/**
 * Read a server-sent event stream from a POST request.
 *
 * EventSource only supports GET without headers, so this reads the response body
 * directly: events are separated by a blank line, each with "event:" and "data:" lines.
 */
export type StreamHandler = (event: string, data: unknown) => void;

export async function postEventStream(
  url: string,
  body: unknown,
  headers: Record<string, string>,
  onEvent: StreamHandler,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream", ...headers },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) {
    throw new StreamUnavailableError(response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      dispatch(block, onEvent);
      boundary = buffer.indexOf("\n\n");
    }
  }
  if (buffer.trim()) dispatch(buffer, onEvent);
}

function dispatch(block: string, onEvent: StreamHandler) {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return;
  try {
    onEvent(event, JSON.parse(data.join("\n")));
  } catch {
    // ignore a malformed event rather than abandoning the whole answer
  }
}

/** The stream endpoint is missing or refused the request: callers fall back to /api/query. */
export class StreamUnavailableError extends Error {
  constructor(public status: number) {
    super(`stream unavailable (${status})`);
  }
}
