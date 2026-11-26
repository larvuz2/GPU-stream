/*
 * This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/.
 */

/**
 * The composer at the foot of the conversation.
 *
 * Enter sends and Shift+Enter starts a new line; Enter that confirms an input method's
 * composition (a word chosen in a Japanese or Chinese IME) does neither. While a turn runs the send
 * button becomes a stop button, since the control plane takes one turn at a time. The field grows
 * with its text up to a limit, then scrolls. Its text is held by the workspace, so a suggestion
 * from elsewhere (the welcome's openings) can fill it.
 *
 * While the agent's open question recommends an answer (`agree`), Enter in the empty field sends
 * that answer: agreeing with the agent is then as short as saying yes, and the field's placeholder
 * says so. Anything typed is sent as it is, as ever.
 * @module
 */
import { useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, Square } from 'lucide-react';
import { ErrorNotice, Notice } from './Notice';
import { turnRunningText } from './useProject';

/** Props of {@link Composer}. */
interface ComposerProps {
  /** The text being written. */
  value: string;
  /** Replaces the text. */
  onChange: (value: string) => void;
  /** Whether a turn is running. */
  running: boolean;
  /** Why nothing can be sent now, or `null` when a message can be. */
  blocked: string | null;
  /** The answer the agent recommends to its open question, which Enter in the empty field sends; `null` for none. */
  agree: string | null;
  /** Sends the text. */
  onSend: (text: string) => Promise<void>;
  /** Stops the running turn. */
  onStop: () => Promise<void>;
}

/**
 * Renders the composer.
 *
 * @param props The component's props.
 * @returns The composer.
 */
export function Composer({ value, onChange, running, blocked, agree, onSend, onStop }: ComposerProps) {
  const fieldId = useId();
  const field = useRef<HTMLTextAreaElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const text = value.trim();
  const idle = blocked === null && !running && !busy;
  const canSend = idle && text !== '';
  const canAgree = idle && text === '' && agree !== null;

  useLayoutEffect(() => {
    const element = field.current;
    if (element !== null) {
      element.style.height = 'auto';
      element.style.height = `${element.scrollHeight}px`;
    }
  }, [value]);

  /**
   * Sends the text and clears the field, or keeps it with the reason it was refused. With the
   * field empty, it sends the answer the agent recommends, where its open question has one.
   */
  async function send(): Promise<void> {
    const message = canSend ? text : canAgree ? agree : null;
    if (message === null) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await onSend(message);
      onChange('');
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
      field.current?.focus();
    }
  }

  /** Stops the turn. */
  async function stop(): Promise<void> {
    setBusy(true);
    setError(null);
    try {
      await onStop();
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  /**
   * Sends on Enter, and leaves Shift+Enter and an input method's Enter to the field.
   *
   * @param event The key press.
   */
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>): void {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      void send();
    }
  }

  const refusal = turnRunningText(error);
  return (
    <div className="mx-auto w-full max-w-[46rem] px-4 pb-4 sm:px-6">
      {blocked === null ? null : (
        <div className="mb-2.5">
          <Notice tone="warn">{blocked}</Notice>
        </div>
      )}
      {error === null ? null : (
        <div className="mb-2.5">
          {refusal === null ? <ErrorNotice error={error} /> : <Notice tone="warn">{refusal}</Notice>}
        </div>
      )}
      <div className="composer">
        <label htmlFor={fieldId} className="sr-only">
          Message the agent
        </label>
        <textarea
          ref={field}
          id={fieldId}
          rows={1}
          placeholder={
            running
              ? 'The agent is working…'
              : canAgree
                ? 'Enter to agree with the recommendation, or answer in your own words'
                : 'Describe what to make next, or answer the agent'
          }
          value={value}
          disabled={blocked !== null}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          onKeyDown={onKey}
        />
        <div className="flex items-center gap-2 px-2.5 pb-2.5">
          <p className="hidden pl-1.5 text-[0.6875rem] text-faint sm:block">
            <kbd className="font-sans">Enter</kbd> to send · <kbd className="font-sans">Shift</kbd>+
            <kbd className="font-sans">Enter</kbd> for a new line
          </p>
          {running ? (
            <button
              type="button"
              className="send-btn send-btn-stop ml-auto"
              aria-label="Stop the agent"
              title="Stop the agent"
              disabled={busy}
              onClick={() => {
                void stop();
              }}
            >
              <Square className="size-3.5 fill-current" aria-hidden="true" />
            </button>
          ) : (
            <button
              type="button"
              className="send-btn ml-auto"
              aria-label="Send"
              title="Send"
              disabled={!canSend}
              onClick={() => {
                void send();
              }}
            >
              {busy ? (
                <span className="spinner size-3.5" aria-hidden="true" />
              ) : (
                <ArrowUp className="size-4" aria-hidden="true" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
