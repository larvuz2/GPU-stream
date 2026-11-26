# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Tests of the Cut Room scripts' own logic: what they compute before FFmpeg or a speech model is asked anything.

Timelines, caption grouping, layouts of text, filter graphs, the parsing of
what FFmpeg prints, the key, and the bit rate that fits a size. Nothing here
runs FFmpeg or loads a model: what those do with what the scripts hand them
is proven on a running engine, by the recipes of `moody/skills/cutroom`.

The scripts import one another by name, as they do where `cutroom` runs
them, so their folder goes on the path first. NumPy and Pillow are needed for
the scripts that use them; a machine without one skips those tests, saying
which is missing. Run with `pytest addons/modal/cutroom`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import check  # noqa: E402
import cut  # noqa: E402
import explainer  # noqa: E402
import fit  # noqa: E402
import join  # noqa: E402
import narrate  # noqa: E402
import sheet  # noqa: E402

EBUR128 = """
[Parsed_ebur128_1 @ 0x55] t: 2.9 TARGET:-23 LUFS M: -13.1 S: -14.0 I: -14.9 LUFS LRA: 1.0 LU
[Parsed_volumedetect_0 @ 0x55] mean_volume: -16.5 dB
[Parsed_volumedetect_0 @ 0x55] max_volume: -0.6 dB
[Parsed_ebur128_1 @ 0x55] Summary:

  Integrated loudness:
    I:         -13.0 LUFS
    Threshold: -23.3 LUFS

  Loudness range:
    LRA:         4.1 LU
    Threshold: -33.3 LUFS
    LRA low:   -16.4 LUFS
    LRA high:  -12.3 LUFS

  True peak:
    Peak:       -0.6 dBFS
"""


def words(*items: tuple[str, float, float]) -> list[dict]:
    """Transcript words from (word, start, end)."""
    return [{"w": w, "s": s, "e": e} for w, s, e in items]


def events(ass: str, style: str) -> list[str]:
    """The text of a subtitle file's events of one style, without their override tags."""
    import re

    lines = [
        line
        for line in ass.splitlines()
        if line.startswith("Dialogue:") and f",{style}," in line
    ]
    return [re.sub(r"\{[^}]*\}", "", line.split(",", 9)[-1]) for line in lines]


def test_segments_are_source_seconds_each_with_a_speed():
    assert cut.parse_segments("12-20, 7.3-9.3@0.5,0-9@3") == [
        (12, 20, 1.0),
        (7.3, 9.3, 0.5),
        (0, 9, 3.0),
    ]
    assert cut.parse_segments("") == []


def test_words_move_onto_the_timeline_the_kept_parts_make():
    spoken = words(
        ("skipped", 1.0, 1.4),
        ("slow", 10.0, 10.5),
        ("fast", 22.0, 23.0),
        ("late", 23.9, 24.6),
    )
    moved, total = cut.remap_words(spoken, [(20.0, 24.0, 2.0), (10.0, 11.0, 0.5)])
    assert total == pytest.approx(4.0)
    assert [(w["w"], w["s"], w["e"]) for w in moved] == [
        ("fast", 1.0, 1.5),
        ("late", 1.95, 2.0),
        ("slow", 2.0, 3.0),
    ], (
        "a part played at twice the speed halves its words' times, a word is cut off where its part ends, and a "
        "word outside every part is gone"
    )


def test_caption_lines_become_words_spread_over_each_lines_time():
    spread = cut.lines_to_words([[2.0, 4.0, "one two", "8FE6FF"], [5.0, 5.5, "three"]])
    assert [(w["w"], w["s"], w["e"], w.get("c")) for w in spread] == [
        ("one", 2.0, 3.0, "8FE6FF"),
        ("two", 3.0, 4.0, "8FE6FF"),
        ("three", 5.0, 5.5, None),
    ]


def test_captions_show_three_words_at_a_time_with_the_spoken_one_highlighted_and_swears_left_out():
    spoken = words(
        ("Wait,", 0.0, 0.3),
        ("what", 0.9, 1.1),
        ("is", 1.1, 1.2),
        ("that", 1.2, 1.4),
        ("shit?", 1.4, 1.7),
    )
    ass = cut.build_ass(spoken, 0.0, 5.0, "A hook", 1380, font="Inter Black")
    shown = events(ass, "Cap")
    assert shown == ["WAIT,", "WHAT IS THAT…?", "WHAT IS THAT…?", "WHAT IS THAT…?"], (
        "punctuation ends a group, a group has three words at most, each word of a group is one event, and a swear "
        "is dropped with its punctuation kept"
    )
    highlighted = [line for line in ass.splitlines() if ",Cap," in line]
    assert (
        highlighted[1].count("\\c&H0000E5FF&") == 1
        and "{\\c&H0000E5FF&}WHAT" in highlighted[1]
    )
    assert "{\\c&H0000E5FF&}IS" in highlighted[2]
    assert (
        events(ass, "Hook") == ["A hook"]
        and "Inter Black" in ass
        and "Arial Black" not in ass
    )


def test_a_hook_stays_for_the_whole_clip_when_its_seconds_are_zero_and_a_title_replaces_it():
    whole = cut.build_ass([], 10.0, 25.0, "Stay", 1420, hook_secs=0, font="Inter Black")
    assert "Dialogue: 1,0:00:00.00,0:00:15.00,Hook" in whole
    titled = cut.build_ass(
        [],
        0.0,
        9.0,
        "Hook",
        1560,
        title=("box", "A TITLE on the seam", 730, 0),
        font="Inter Black",
    )
    assert (
        events(titled, "TitleBox") == ["A TITLE on the seam"]
        and events(titled, "Hook") == []
    )


def test_the_focus_window_glides_between_keyframes_and_holds_outside_them():
    expression = cut.focus_x("0:0.5,4:0.62", "W").replace("\\,", ",")
    assert (
        expression.startswith("max(0,min(iw-W,")
        and "if(lt(t,0.0),(iw*0.5000-W/2)," in expression
    )
    assert "(iw*0.5000-W/2)+((iw*0.6200-W/2)-(iw*0.5000-W/2))*(t-0.0)/4.0" in expression
    assert cut.focus_x("0:0.5,4:0.62", "W").count(",") == cut.focus_x(
        "0:0.5,4:0.62", "W"
    ).count("\\,"), "every comma is escaped, or the filter graph ends at it"


def test_text_wraps_at_spaces_and_timestamps_are_in_centiseconds():
    assert cut.wrap("This fractal never ENDS", 22) == ["This fractal never", "ENDS"]
    assert cut.ts(3725.5) == "1:02:05.50" and cut.ts(-1) == "0:00:00.00"
    assert cut.esc("a{b}\\c\nd") == "a(b)c d"


def test_a_layouts_filter_graph_ends_in_the_captioned_picture():
    graph = cut.video_filter("focus", "", "jobs/a b/clip.ass", focus="0:0.4")
    assert graph.endswith(";[v]fps=30,subtitles='jobs/a b/clip.ass'[vo]")
    assert (
        f"scale={cut.W}:{cut.FOCUS_H}" in graph
        and f"overlay=0:{cut.FOCUS_Y}[v]" in graph
    )
    trimmed = cut.video_filter("blur", "", "c.ass", trim_bottom=0.15)
    assert trimmed.startswith("[0:v]crop=iw:floor(ih*0.850/2)*2:0:0[trim];[trim]split")


def test_an_explainers_subtitles_are_sentences_timed_by_their_length():
    parts = explainer.chunks(
        "One short. A second sentence, three times as long as it.", 0.0, 8.0
    )
    assert [text for _, _, text in parts] == [
        "One short.",
        "A second sentence, three times as long as it.",
    ]
    assert parts[0][1] == pytest.approx(parts[1][0]) and parts[1][1] == pytest.approx(
        8.0
    )
    assert parts[0][1] < 2.0, "a sentence gets time in proportion to its length"
    long = explainer.chunks("word " * 40, 0.0, 10.0)
    assert len(long) > 1 and all(len(text) <= 84 for _, _, text in long)
    assert explainer.wrap2("short") == "short"
    assert (
        explainer.wrap2("The test pattern plays at three times the speed.").count("\\N")
        == 1
    )


def test_a_headline_is_words_each_at_its_second_with_a_bar_starting_a_line():
    assert explainer.parse_title_words("THE@4.72, CLOWN@5.18,|GOT@5.66") == [
        ("THE", 4.72, False),
        ("CLOWN", 5.18, False),
        ("GOT", 5.66, True),
    ]


def test_sped_up_parts_are_badged_at_their_place_in_the_output():
    fast, total = explainer.fast_parts(
        [(32.0, 36.0, 1.0), (0.0, 19.0, 4.0), (20.0, 26.0, 4.0), (40.0, 41.0, 0.5)]
    )
    assert fast == [(4.0, 8.75, 4.0), (8.75, 10.25, 4.0)] and total == pytest.approx(
        12.25
    ), "a part at half speed is longer in the output and gets no badge"


def test_an_explainer_leaves_out_the_subtitle_its_headline_already_says():
    pytest.importorskip("PIL", reason="Pillow lays out the headline")
    lines = [
        [4.2, 6.4, "This week, the boss got meaner."],
        [7.2, 9.0, "We animated a new attack."],
    ]
    ass = explainer.build_ass(
        lines,
        "",
        "",
        [(0.0, 3.0, 3.0)],
        words="THE@4.7,BOSS@5.2,|GOT@5.6,MEANER@5.9",
        words_end=7.0,
    )
    assert events(ass, "Sub") == ["We animated a new attack."]
    assert events(ass, "Big") == ["THE", "BOSS", "GOT", "MEANER"] and events(
        ass, "Badge"
    ) == ["3× SPEED"]
    assert events(ass, "Tag") == [] and events(ass, "Title") == [], (
        "the tag and the small title are off unless given"
    )
    big = [line for line in ass.splitlines() if ",Big," in line]
    heights = [line.split("\\pos(")[1].split(")")[0].split(",")[1] for line in big]
    assert heights[0] == heights[1] != heights[2] == heights[3], (
        "the bar starts the second line"
    )
    assert all(",0:00:07.00,Big" in line for line in big), (
        "every word leaves at the headline's end"
    )


def test_music_is_ducked_by_the_voice_and_the_mix_is_normalized_once():
    plain = explainer.audio_graph(0.2, None, 30.0)
    assert (
        plain
        == "[0:a]volume=0.2[bed];[1:a]apad[vox];[bed][vox]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[ao]"
    )
    scored = explainer.audio_graph(0.2, 0.16, 30.0)
    assert (
        "[2:a]aresample=48000,volume=0.16,afade=t=in:d=1.2,afade=t=out:st=28.20:d=1.8[mus]"
        in scored
    )
    assert (
        "[mus][key]sidechaincompress=threshold=0.015:ratio=5:attack=40:release=450[md]"
        in scored
    )
    assert scored.count("loudnorm") == 1 and scored.endswith("[ao]")


def test_narration_lines_never_overlap_unless_one_has_no_caption():
    lines = [
        {"text": "First.", "at": 0.2},
        {"text": "Too early.", "at": 1.0},
        {"text": "Ha!", "caption": "", "at": 1.5},
        {"text": "Next."},
    ]
    placed = narrate.place(lines, [2.0, 1.0, 0.5, 1.0], gap=0.25)
    assert placed == [(0.2, 2.2), (2.45, 3.45), (1.5, 2.0), (3.7, 4.7)], (
        "a captioned line waits for the one before it and its gap; a shout lies where it says and moves nothing"
    )


def test_the_voice_track_delays_each_take_to_its_start():
    graph = narrate.mix_graph([0.3, 4.2], master=False)
    assert (
        graph
        == "[0:a]adelay=300:all=1[d0];[1:a]adelay=4200:all=1[d1];[d0][d1]amix=inputs=2:normalize=0:duration=longest[v]"
    )
    mastered = narrate.mix_graph([0.0], master=True)
    assert mastered.endswith(f"[m];[m]{narrate.MASTER}[v]")


def test_a_rules_file_sets_only_what_it_names():
    rules, read = check.parse_rules(None)
    assert not read and (
        rules["min"],
        rules["max"],
        rules["tags"],
        rules["mention"],
        rules["banned"],
    ) == (7.0, 60.0, [], None, [])


def test_a_rules_file_is_read_line_by_line(tmp_path):
    file = tmp_path / "rules.md"
    file.write_text(
        "# Terms\nmin_seconds: 15\nrequired_hashtags: #One #two\nrequired_mention: @someone\nbanned_terms: Free Download, giveaway\n"
    )
    rules, read = check.parse_rules(str(file))
    assert read and rules["min"] == 15.0 and rules["max"] == 60.0
    assert rules["tags"] == ["#One", "#two"] and rules["mention"] == "@someone"
    assert check.banned_in("A FREE download inside", rules["banned"]) == [
        "free download"
    ]


def test_the_loudness_read_is_the_summarys_not_a_moments():
    assert check.integrated_lufs(EBUR128) == -13.0, (
        "the running value before the summary is not the answer"
    )
    assert check.integrated_lufs("no sound here") is None
    assert (
        check.fps_of("30000/1001") == pytest.approx(29.97, abs=0.01)
        and check.fps_of("0/0") == 0.0
    )
    assert check.parse_range("-13:-17") == (-17.0, -13.0) and check.parse_size(
        "1920x1080"
    ) == (1920, 1080)


def test_a_contact_sheets_label_is_the_second_in_the_source():
    assert sheet.time_label(0, 1) == "%{eif\\:trunc(t+0)\\:d}"
    close = sheet.time_label(9, 0.5)
    assert (
        close.startswith("%{eif\\:trunc(t+9)\\:d}.")
        and "mod(trunc((t+9)*10)\\,10)" in close
    ), "frames closer than a second show a tenth, and the seek's start is added back"
    assert (
        sheet.sheet_count(70, 1, 8, 8) == 2
        and sheet.sheet_count(30, 1, 6, 5) == 1
        and sheet.sheet_count(3, 0.5, 6, 1) == 1
    )


def test_scene_cuts_black_and_volume_are_read_from_what_ffmpeg_prints():
    log = (
        "[Parsed_showinfo_1 @ 0x1] n:   0 pts: 128000 pts_time:10 duration: 512\n"
        "[Parsed_showinfo_1 @ 0x1] n:   1 pts: 256000 pts_time:20.3333 duration: 512\n"
        "[blackdetect @ 0x2] black_start:4.5 black_end:5.25 black_duration:0.75\n"
    )
    assert sheet.scene_times(log) == [10.0, 20.333]
    assert sheet.black_spans(log) == [(4.5, 5.25)]
    assert sheet.volume(EBUR128) == {"mean_db": -16.5, "max_db": -0.6}
    assert sheet.stack_layout(6, 4) == "0_0|w0_0|w0+w0_0|w0+w0+w0_0|0_h0|w0_h0"


def test_the_bit_rate_that_fits_a_size_is_what_the_sound_and_the_container_leave():
    assert fit.video_kbps(18.2, 37.76, 128) == 3715, (
        "the settled encode: 18.2 MB over 37.76 s with 128 kb/s of sound"
    )
    assert fit.video_kbps(18.2, 30.0, 160) == 4681
    assert fit.video_kbps(1.0, 600.0, 160) < fit.LOWEST_KBPS


def test_joined_clips_start_where_the_ones_before_them_end():
    assert join.offsets([56.4, 52.267, 10.0]) == [0.0, 56.4, 108.667]
    graph = join.graph(2, 1920, 1080, [False, True])
    assert "[0:a]aresample=48000" in graph and "[2:a]aresample=48000" in graph, (
        "a silent clip takes the silence made for it"
    )
    assert graph.endswith("[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]")


def test_swears_are_known_in_two_languages_and_harmless_words_pass():
    np = pytest.importorskip("numpy", reason="clean.py reads samples with NumPy")
    assert np is not None
    import clean

    assert all(
        clean.is_bad(word) for word in ("Damn!", "f*ck", "mierda,", "PENDEJO", "sh*t")
    )
    assert not any(
        clean.is_bad(word)
        for word in ("wey", "manches", "class", "assess", "hello", "shell", "")
    )
    dropped = clean.drop_bad(
        words(
            ("What", 0.0, 0.2),
            ("the", 0.2, 0.3),
            ("hell?", 0.3, 0.6),
            ("Go.", 2.0, 2.2),
        )
    )
    assert [(w["w"], w["e"]) for w in dropped] == [
        ("What", 0.2),
        ("the…?", 0.6),
        ("Go.", 2.2),
    ]


def test_mutes_are_widened_joined_and_written_as_one_filter():
    pytest.importorskip("numpy", reason="clean.py reads samples with NumPy")
    import clean

    assert clean.merge([(1.0, 1.4), (1.5, 2.0), (5.0, 5.2)]) == [
        (0.88, 2.12),
        (4.88, 5.32),
    ]
    assert (
        clean.mute_filter([(0.88, 2.12), (4.88, 5.32)])
        == "volume=0:enable='between(t,0.88,2.12)+between(t,4.88,5.32)'"
    )
    assert clean.mute_filter([]) == ""


def test_moments_are_the_best_stretches_snapped_to_words_and_never_overlapping():
    np = pytest.importorskip("numpy", reason="moments.py scores with NumPy")
    import moments

    score = np.zeros(120)
    score[[30, 31, 90]] = [5.0, 4.0, 3.0]
    spoken = words(
        ("Wait", 24.0, 24.4),
        ("what", 24.4, 24.8),
        ("now", 35.0, 35.5),
        ("later", 88.0, 88.6),
    )
    picks = moments.pick_windows(score, spoken, 120.0, top=5, shortest=8, longest=12)
    assert [(p["start"], p["end"], p["peak"]) for p in picks] == [
        (23.7, 31.7, 30),
        (87.7, 95.7, 90),
    ], (
        "a stretch starts just before its first word, is stretched to the shortest allowed where its words end "
        "early, and a peak whose stretch touches one already taken is skipped"
    )
    assert moments.smooth(np.ones(3), 30).shape == (3,), (
        "a kernel longer than the signal keeps its length"
    )
    assert not moments.z(np.ones(5)).any()


def test_a_sign_is_cut_out_of_green_or_magenta_with_a_soft_edge_and_no_fringe():
    np = pytest.importorskip("numpy", reason="key.py computes the key with NumPy")
    pytest.importorskip("PIL", reason="key.py reads pictures with Pillow")
    import key

    green = np.zeros((40, 40, 3), np.uint8)
    green[...] = (0, 255, 0)
    green[10:30, 10:30] = (200, 120, 40)
    green[10, 10] = (100, 190, 20)
    assert key.background(green) == "green"
    cut_out = key.key(green, "green")
    assert cut_out[0, 0, 3] == 0 and cut_out[20, 20].tolist() == [200, 120, 40, 255]
    edge = cut_out[10, 10]
    assert 0 < edge[3] < 255 and edge[1] <= max(edge[0], edge[2]), (
        "an edge pixel is partly clear and loses its green"
    )
    magenta = np.zeros((40, 40, 3), np.uint8)
    magenta[...] = (255, 0, 255)
    magenta[10:30, 10:30] = (40, 160, 60)
    assert key.background(magenta) == "magenta"
    leaves = key.key(magenta, "magenta")
    assert leaves[0, 0, 3] == 0 and leaves[20, 20].tolist() == [40, 160, 60, 255], (
        "green art survives a magenta key"
    )
    with pytest.raises(ValueError):
        key.background(np.full((40, 40, 3), 128, np.uint8))


def test_levels_reads_the_summary_and_measures_a_stretch():
    np = pytest.importorskip("numpy", reason="levels.py measures with NumPy")
    import levels

    assert levels.summary(EBUR128) == {"lufs": -13.0, "lra": 4.1, "true_peak_db": -0.6}
    assert levels.parse_spans("6.7-10.7, 23.3-25.2") == [(6.7, 10.7), (23.3, 25.2)]
    assert levels.rms_db(np.full(1000, 0.5, np.float32)) == pytest.approx(-6.0, abs=0.1)
    assert levels.rms_db(np.zeros(0, np.float32)) == -180.0


def test_a_sign_pops_in_past_its_size_and_settles():
    pytest.importorskip("PIL", reason="reveal.py draws with Pillow")
    import reveal

    assert reveal.pop(0) == 0 and reveal.pop(-1) == 0 and reveal.pop(1.0) == 1.0
    scales = [reveal.pop(reveal.POP_SECONDS * step / 20) for step in range(1, 21)]
    assert scales[0] > 0.55 and max(scales) > 1.0 and scales[-1] == 1.0, (
        "it overshoots before it settles"
    )
    assert reveal.parse_sign("art/sign@2x.png@1.9") == ("art/sign@2x.png", 1.9)
    assert (
        reveal.parse_sign("art/sign.png")[1] != reveal.parse_sign("art/sign.png")[1]
    ), "no second is not a number"
