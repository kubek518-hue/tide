// Supabase Edge Function: stripe-webhook
// Flips a member to active when their Stripe Checkout payment completes.
// Free tier covers this comfortably. Deploy steps are in the README (Phase 2).
//
// Secrets required (supabase secrets set ...):
//   STRIPE_WEBHOOK_SECRET  - from the Stripe webhook endpoint you create
//   SB_URL                 - your project URL
//   SB_SERVICE_ROLE_KEY    - Settings -> API -> service_role (server-only key)

const enc = new TextEncoder();

async function validSignature(body: string, sigHeader: string, secret: string) {
  const parts = Object.fromEntries(
    sigHeader.split(",").map((kv) => kv.split("=") as [string, string]),
  );
  const t = parts["t"];
  const v1 = parts["v1"];
  if (!t || !v1) return false;
  // Reject events older than 5 minutes (replay protection)
  if (Math.abs(Date.now() / 1000 - Number(t)) > 300) return false;
  const key = await crypto.subtle.importKey(
    "raw", enc.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(`${t}.${body}`));
  const hex = [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, "0")).join("");
  return hex === v1;
}

Deno.serve(async (req) => {
  const secret = Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "";
  const sig = req.headers.get("stripe-signature") ?? "";
  const body = await req.text();

  if (!(await validSignature(body, sig, secret))) {
    return new Response("bad signature", { status: 400 });
  }

  const event = JSON.parse(body);
  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const email = (session.customer_details?.email ?? session.customer_email ?? "")
      .toLowerCase().trim();
    if (email) {
      const r = await fetch(`${Deno.env.get("SB_URL")}/rest/v1/members?on_conflict=email`, {
        method: "POST",
        headers: {
          apikey: Deno.env.get("SB_SERVICE_ROLE_KEY")!,
          Authorization: `Bearer ${Deno.env.get("SB_SERVICE_ROLE_KEY")!}`,
          "Content-Type": "application/json",
          Prefer: "resolution=merge-duplicates",
        },
        body: JSON.stringify({
          email,
          active: true,
          plan: session.metadata?.plan ?? "early",
          stripe_customer: session.customer ?? null,
        }),
      });
      if (!r.ok) {
        console.error("member upsert failed", r.status, await r.text());
        return new Response("upsert failed", { status: 500 });
      }
      console.log("member activated:", email);
    }
  }
  return new Response("ok", { status: 200 });
});
