import { useState, useCallback, useRef } from 'react';
import { explainApi } from '@/services/api';

export function useLLMExplain(
  subject: 'plan' | 'mission' | 'anomaly',
  id: string | null,
) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const trigger = useCallback(() => {
    if (!id) return;

    // Close any previous stream.
    if (esRef.current) {
      esRef.current.close();
    }

    setText('');
    setError(null);
    setLoading(true);

    const es = explainApi.llmStream(subject, id);
    esRef.current = es;

    es.onmessage = (ev) => {
      if (ev.data === '[DONE]') {
        setLoading(false);
        es.close();
        return;
      }
      try {
        const parsed = JSON.parse(ev.data) as { text: string };
        setText(prev => prev + parsed.text);
      } catch {
        // ignore malformed frames
      }
    };

    es.onerror = () => {
      setError('Stream error — check server logs.');
      setLoading(false);
      es.close();
    };
  }, [subject, id]);

  const reset = useCallback(() => {
    if (esRef.current) esRef.current.close();
    setText('');
    setError(null);
    setLoading(false);
  }, []);

  return { text, loading, error, trigger, reset };
}
