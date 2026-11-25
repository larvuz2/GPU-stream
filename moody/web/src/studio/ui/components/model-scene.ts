/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The three.js scene behind a card's 3D model: a glTF model, a camera on orbit controls, and
 * the light they are seen in.
 *
 * This module and `ModelStage.tsx`, which drives it, are the only ones that import three.js, and
 * they are fetched lazily (`Model.tsx`), so the library is downloaded when a card first shows a
 * model and by nobody else.
 *
 * The model is fitted to the stage whatever its size: it is centered on its bounding box, and the
 * camera stands off by the distance at which its bounding sphere fills the view, so a zoom of 1
 * always frames the whole of it. A view is two angles and that zoom (`ModelView`): `azimuth`
 * around the model from its front, `elevation` above its middle.
 *
 * A finish replaces the model's own materials with one material of a color, which is how a card
 * shows a form in clay before anyone argues about its paint. {@link FINISHES} has an entry per
 * finish of the catalog and fails to compile while one is missing. Light comes from a small room
 * environment generated in the browser, so metal has something to reflect and no file is fetched
 * for it.
 *
 * Nothing is drawn that has not changed. The scene renders a frame when the view, the size, or
 * the finish changes, and keeps rendering only while the model turns by itself or the controls
 * are still settling, and only while the stage is on screen: a model scrolled out of view costs
 * nothing until it is scrolled back.
 * @module
 */
import {
  ACESFilmicToneMapping,
  Box3,
  Color,
  DirectionalLight,
  MathUtils,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  PMREMGenerator,
  Scene,
  Sphere,
  Spherical,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
  type Material,
  type Mesh,
  type Object3D,
  type WebGLRenderTarget,
} from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import type { FinishName } from '../catalog';
import { clamp, type ModelView } from '../values';

/** The camera's field of view, in degrees: long enough a lens that the model is not distorted. */
const FIELD_OF_VIEW = 32;

/** How far the camera stands at zoom 1, as a share of the distance at which the bounding sphere just fits. */
const MARGIN = 0.94;

/** How strongly the room lights the model: enough to read its form, short of washing out its paint. */
const ROOM_LIGHT = 0.55;

/** The nearest and farthest the person can zoom. */
const ZOOM = { min: 0.5, max: 4 };

/** The steepest the view looks down or up at the model, in degrees. */
const ELEVATION_LIMIT = 85;

/** How fast a model turns by itself, in the controls' units: a turn in about a minute at 1. */
const SPIN_SPEED = 1.4;

/** The material each finish gives the whole model, or `null` to keep the model's own. */
const FINISHES: Record<FinishName, ((color: Color) => Material) | null> = {
  original: null,
  clay: (color) => new MeshStandardMaterial({ color, roughness: 0.95, metalness: 0 }),
  metal: (color) => new MeshStandardMaterial({ color, roughness: 0.32, metalness: 1 }),
  gloss: (color) =>
    new MeshPhysicalMaterial({ color, roughness: 0.25, metalness: 0, clearcoat: 1, clearcoatRoughness: 0.08 }),
  wire: (color) => new MeshStandardMaterial({ color, roughness: 1, metalness: 0, wireframe: true }),
};

/**
 * Whether an object of a scene is a mesh.
 *
 * @param object The object.
 * @returns `true` for a mesh, by the mark three.js gives one.
 */
function isMesh(object: Object3D): object is Mesh {
  return 'isMesh' in object && object.isMesh === true;
}

/** How the person may move the view. */
export interface SceneMotion {
  /** Whether the view is fixed. */
  frozen: boolean;
  /** Whether the controls glide to a stop, which is left out where less motion was asked for. */
  glide: boolean;
  /** Whether the model turns by itself until the person takes over. */
  spin: boolean;
}

/** A model on its stage. */
export class ModelScene {
  private readonly renderer: WebGLRenderer;
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(FIELD_OF_VIEW, 1, 0.01, 100);
  private readonly controls: OrbitControls;
  private readonly environment: WebGLRenderTarget;
  private readonly resizing: ResizeObserver;
  private readonly watching: IntersectionObserver;
  private visible = true;
  /** The model's own material of each mesh, to give back when the finish is `original`. */
  private readonly own = new Map<Mesh, Material | Material[]>();
  /** The material of the finish in use, to dispose of when it changes. */
  private finish: Material | null = null;
  /** The distance at which the model's bounding sphere fills the view. */
  private fit = 1;
  private frame = 0;
  private settling = false;
  private disposed = false;

  /**
   * Starts a stage on a canvas.
   *
   * @param canvas The canvas to draw on.
   * @param holder The element whose size the canvas takes.
   * @param onGesture Called with the view each time the person has finished changing it.
   * @throws Where the browser cannot start WebGL.
   */
  constructor(canvas: HTMLCanvasElement, holder: HTMLElement, onGesture: (view: ModelView) => void) {
    this.renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.outputColorSpace = SRGBColorSpace;
    this.renderer.toneMapping = ACESFilmicToneMapping;
    this.environment = new PMREMGenerator(this.renderer).fromScene(new RoomEnvironment(), 0.04);
    this.scene.environment = this.environment.texture;
    this.scene.environmentIntensity = ROOM_LIGHT;
    const key = new DirectionalLight(0xffffff, 2.2);
    key.position.set(2.5, 4, 3);
    this.scene.add(key);

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enablePan = false;
    this.controls.autoRotateSpeed = SPIN_SPEED;
    this.controls.minPolarAngle = MathUtils.degToRad(90 - ELEVATION_LIMIT);
    this.controls.maxPolarAngle = MathUtils.degToRad(90 + ELEVATION_LIMIT);
    this.controls.addEventListener('change', this.invalidate);
    this.controls.addEventListener('start', () => {
      // The person has taken over: the model stops turning by itself.
      this.controls.autoRotate = false;
    });
    this.controls.addEventListener('end', () => {
      onGesture(this.view());
    });

    this.resizing = new ResizeObserver(() => {
      const { width, height } = holder.getBoundingClientRect();
      if (width > 0 && height > 0) {
        this.renderer.setSize(width, height, false);
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.invalidate();
      }
    });
    this.resizing.observe(holder);
    this.watching = new IntersectionObserver((entries) => {
      this.visible = entries.some((entry) => entry.isIntersecting);
      if (this.visible) {
        this.invalidate();
      }
    });
    this.watching.observe(holder);
  }

  /**
   * Loads the model and fits the camera to it.
   *
   * @param url The model's address, a binary glTF.
   * @returns Once the model is on the stage.
   * @throws Where the file cannot be read as glTF.
   */
  async load(url: string): Promise<void> {
    const model = await new GLTFLoader().loadAsync(url);
    if (this.disposed) {
      return;
    }
    const bounds = new Box3().setFromObject(model.scene);
    const sphere = bounds.getBoundingSphere(new Sphere());
    model.scene.position.sub(bounds.getCenter(new Vector3()));
    this.scene.add(model.scene);
    model.scene.traverse((child) => {
      if (isMesh(child)) {
        this.own.set(child, child.material);
      }
    });
    this.fit = (sphere.radius / Math.sin(MathUtils.degToRad(FIELD_OF_VIEW / 2))) * MARGIN;
    this.controls.minDistance = this.fit / ZOOM.max;
    this.controls.maxDistance = this.fit / ZOOM.min;
    this.camera.near = this.fit / 100;
    this.camera.far = this.fit * 10;
    this.camera.updateProjectionMatrix();
  }

  /**
   * Reads where the camera stands.
   *
   * @returns The view, its angles to the degree and its zoom to the hundredth.
   */
  view(): ModelView {
    const distance = this.camera.position.distanceTo(this.controls.target);
    return {
      azimuth: Math.round(MathUtils.radToDeg(this.controls.getAzimuthalAngle())),
      elevation: Math.round(90 - MathUtils.radToDeg(this.controls.getPolarAngle())),
      zoom: Math.round((this.fit / distance) * 100) / 100,
    };
  }

  /**
   * Puts the camera where a view says, and stops the model turning by itself.
   *
   * @param view The view.
   */
  look(view: ModelView): void {
    const distance = this.fit / clamp(view.zoom, ZOOM.min, ZOOM.max);
    const polar = MathUtils.degToRad(90 - clamp(view.elevation, -ELEVATION_LIMIT, ELEVATION_LIMIT));
    this.camera.position.setFromSpherical(new Spherical(distance, polar, MathUtils.degToRad(view.azimuth)));
    this.camera.lookAt(this.controls.target);
    this.controls.update();
    this.invalidate();
  }

  /**
   * Stops the model turning by itself, as when the person takes over by the keyboard.
   */
  hold(): void {
    this.controls.autoRotate = false;
  }

  /**
   * Sets how the person may move the view.
   *
   * @param motion Whether it is fixed, glides, and turns by itself.
   */
  move(motion: SceneMotion): void {
    this.controls.enabled = !motion.frozen;
    this.controls.enableDamping = motion.glide;
    this.controls.autoRotate = motion.spin && !motion.frozen;
    this.invalidate();
  }

  /**
   * Gives the whole model a finish.
   *
   * @param finish The finish.
   * @param color The finish's color, as CSS.
   */
  paint(finish: FinishName, color: string): void {
    const make = FINISHES[finish];
    const material = make === null ? null : make(new Color(color));
    for (const [mesh, original] of this.own) {
      mesh.material = material ?? original;
    }
    this.finish?.dispose();
    this.finish = material;
    this.invalidate();
  }

  /** Frees everything the stage holds on the graphics card. */
  dispose(): void {
    this.disposed = true;
    window.cancelAnimationFrame(this.frame);
    this.resizing.disconnect();
    this.watching.disconnect();
    this.controls.dispose();
    for (const [mesh, material] of this.own) {
      mesh.geometry.dispose();
      for (const one of Array.isArray(material) ? material : [material]) {
        one.dispose();
      }
    }
    this.finish?.dispose();
    this.environment.dispose();
    this.renderer.dispose();
  }

  /** Asks for a frame. */
  private readonly invalidate = (): void => {
    if (this.frame === 0 && !this.disposed) {
      this.frame = window.requestAnimationFrame(this.draw);
    }
  };

  /** Draws a frame, and another while the controls move the camera or the model turns. */
  private readonly draw = (): void => {
    this.frame = 0;
    const moved = this.controls.update();
    this.renderer.render(this.scene, this.camera);
    if (this.visible && (moved || this.controls.autoRotate || this.settling)) {
      this.settling = moved;
      this.frame = window.requestAnimationFrame(this.draw);
    }
  };
}
