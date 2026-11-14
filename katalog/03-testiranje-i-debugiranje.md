# Testiranje i debugiranje

Testovi, traženje uzroka grešaka i provjera da stvari stvarno rade.

[← Natrag na katalog](README.md)

## Agenti

| Agent | Za šta služi |
|---|---|
| [`test-engineer`](../.claude/agents/test-engineer.md) | Unit, integration i e2e testovi |
| [`tdd-orchestrator`](../.claude/agents/tdd-orchestrator.md) | Disciplina red-green-refactor |
| [`debugger`](../.claude/agents/debugger.md) | Pronalazi uzrok greške i popravlja je |
| [`ui-visual-validator`](../.claude/agents/ui-visual-validator.md) | Vizualna provjera sučelja kroz screenshotove |

## Skillovi

| Skill | Izvor | Za šta služi |
|---|---|---|
| [`test-driven-development`](../.claude/skills/test-driven-development/SKILL.md) | agent-skills (Addy Osmani) | Petlja red-green-refactor |
| [`systematic-debugging`](../.claude/skills/systematic-debugging/SKILL.md) | superpowers | Sustavno traženje uzroka prije popravka |
| [`verification-before-completion`](../.claude/skills/verification-before-completion/SKILL.md) | superpowers | Pokreni provjere prije nego kažeš "gotovo" |
| [`webapp-testing`](../.claude/skills/webapp-testing/SKILL.md) | Anthropic | Testiranje web aplikacija s Playwrightom |
