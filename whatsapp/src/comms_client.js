/**
 * Cliente HTTP hacia el Comms Service (F3-T4). Usa `fetch` nativo (Node >= 18) — sin
 * dependencias extra solo para esto.
 */
export function createCommsClient(baseUrl) {
  return {
    async sendInbound(payload) {
      const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/comms/inbound`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const body = await response.text();
        throw new Error(`comms respondió ${response.status}: ${body}`);
      }
      return response.json();
    },
  };
}
