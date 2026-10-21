// Vercel function: coach briefing via Mistral (same prompt as app/llm.py). Key: MISTRAL_API_KEY env var on Vercel.
const SYSTEM = "Tu es l'assistant d'un coordinateur offensif NFL. On te donne une recommandation de chip et des taux " +
  "observés (NGS/PFF 2021). Reformule-la en exactement deux phrases courtes, en français, à l'impératif, " +
  "comme un coach parle à ses joueurs, avec des mots simples de football. Cite les deux taux de pression " +
  "(sans chip, avec chip) et le plan B s'il est fourni. N'invente aucun chiffre. Pas de guillemets.";

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST uniquement" });
  const { facts = "", fallback = "" } = req.body || {};
  const key = process.env.MISTRAL_API_KEY, model = process.env.MISTRAL_MODEL || "mistral-large-latest";
  if (!key) return res.json({ text: fallback, source: "texte de secours (pas de clé Mistral)" });
  try {
    const r = await fetch("https://api.mistral.ai/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ model, max_tokens: 200, messages: [
        { role: "system", content: SYSTEM }, { role: "user", content: String(facts).slice(0, 4000) }] }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const text = (await r.json()).choices[0].message.content.trim().replace(/^["«»\s]+|["«»\s]+$/g, "");
    res.json(text ? { text, source: `Mistral (${model})` } : { text: fallback, source: "texte de secours (réponse vide)" });
  } catch (e) {
    res.json({ text: fallback, source: `texte de secours (erreur Mistral : ${e.message})` });
  }
};
