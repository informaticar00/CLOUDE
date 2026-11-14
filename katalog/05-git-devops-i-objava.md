# Git, DevOps i objava

Grane, pull requestovi, CI/CD i puštanje u produkciju.

[← Natrag na katalog](README.md)

## Agenti

| Agent | Za šta služi |
|---|---|
| [`git-workflow-manager`](../.claude/agents/git-workflow-manager.md) | Strategija grananja i spajanja |
| [`devops-engineer`](../.claude/agents/devops-engineer.md) | Docker, GitHub Actions, cloud, deploy |
| [`kubernetes-specialist`](../.claude/agents/kubernetes-specialist.md) | Kubernetes klasteri i workloadi |
| [`terraform-engineer`](../.claude/agents/terraform-engineer.md) | Infrastruktura kao kod (Terraform) |
| [`sre-engineer`](../.claude/agents/sre-engineer.md) | Pouzdanost, SLO-ovi, incidenti |

## Skillovi

| Skill | Izvor | Za šta služi |
|---|---|---|
| [`git-workflow-and-versioning`](../.claude/skills/git-workflow-and-versioning/SKILL.md) | agent-skills (Addy Osmani) | Commitovi, grane i konflikti |
| [`git-guardrails-claude-code`](../.claude/skills/git-guardrails-claude-code/SKILL.md) | Matt Pocock | Hookovi koji blokiraju opasne git naredbe |
| [`using-git-worktrees`](../.claude/skills/using-git-worktrees/SKILL.md) | superpowers | Izolirani radni prostor za novu funkciju |
| [`finishing-a-development-branch`](../.claude/skills/finishing-a-development-branch/SKILL.md) | superpowers | Što napraviti s gotovom granom |
| [`pr`](../.claude/skills/pr/SKILL.md) | Matt Pocock | Napiši opis pull requesta |
| [`triage`](../.claude/skills/triage/SKILL.md) | Matt Pocock | Razvrstavanje issueova i vanjskih PR-ova |
| [`setup-pre-commit`](../.claude/skills/setup-pre-commit/SKILL.md) | Matt Pocock | Husky pre-commit: Prettier, tipovi, testovi |
| [`setup-matt-pocock-skills`](../.claude/skills/setup-matt-pocock-skills/SKILL.md) | Matt Pocock | Pripremi repo za Matt Pocock skillove |
| [`ci-cd-and-automation`](../.claude/skills/ci-cd-and-automation/SKILL.md) | agent-skills (Addy Osmani) | Postavljanje build i deploy pipelinea |
| [`shipping-and-launch`](../.claude/skills/shipping-and-launch/SKILL.md) | agent-skills (Addy Osmani) | Priprema za puštanje u produkciju |
| [`deploy-to-vercel`](../.claude/skills/deploy-to-vercel/SKILL.md) | Vercel | Objavi aplikaciju ili stranicu na Vercelu |
| [`vercel-cli-with-tokens`](../.claude/skills/vercel-cli-with-tokens/SKILL.md) | Vercel | Vercel CLI s tokenom: deploy, varijable okruženja |
| [`wizard`](../.claude/skills/wizard/SKILL.md) | Matt Pocock | Interaktivni bash vodič za korake koje samo čovjek može napraviti |
