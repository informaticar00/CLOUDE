# Code review i kvaliteta

Pregled koda, sigurnost i čišćenje tehničkog duga.

[← Natrag na katalog](README.md)

## Agenti

| Agent | Za šta služi |
|---|---|
| [`code-reviewer`](../.claude/agents/code-reviewer.md) | Pregled koda: greške, sigurnost, kvaliteta (samo čita) |
| [`security-auditor`](../.claude/agents/security-auditor.md) | Sigurnosni pregled: OWASP, tajni ključevi, ovisnosti |
| [`threat-modeling-expert`](../.claude/agents/threat-modeling-expert.md) | Modeliranje prijetnji (STRIDE, attack trees) |
| [`accessibility-auditor`](../.claude/agents/accessibility-auditor.md) | Pristupačnost po WCAG 2.2 AA |

## Skillovi

| Skill | Izvor | Za šta služi |
|---|---|---|
| [`requesting-code-review`](../.claude/skills/requesting-code-review/SKILL.md) | superpowers | Zatraži pregled kad završiš veći posao |
| [`receiving-code-review`](../.claude/skills/receiving-code-review/SKILL.md) | superpowers | Kako kritički primiti komentare s pregleda |
| [`doubt-driven-development`](../.claude/skills/doubt-driven-development/SKILL.md) | agent-skills (Addy Osmani) | Svaka važna odluka prolazi kroz "đavoljeg odvjetnika" |
| [`ponytail`](../.claude/skills/ponytail/SKILL.md) | ponytail | Lijeni senior: najmanja promjena koja rješava zadatak |
| [`ponytail-review`](../.claude/skills/ponytail-review/SKILL.md) | ponytail | Pregled jedne promjene: logika, sigurnost, brzina |
| [`ponytail-audit`](../.claude/skills/ponytail-audit/SKILL.md) | ponytail | Pregled cijelog repozitorija: bugovi, rupe, spori dijelovi |
| [`ponytail-debt`](../.claude/skills/ponytail-debt/SKILL.md) | ponytail | Popis svih prečaca (`shortcut:` komentara) kao duga |
