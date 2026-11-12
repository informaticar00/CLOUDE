# Claude Code agenti

Agenti se nalaze u `.claude/agents/`. Claude ih bira automatski prema opisu zadatka, a možeš ih pozvati i po imenu, npr.:
"Koristi **code-reviewer** agenta da pregleda moje izmjene."

## Programiranje
| Agent | Za šta služi |
|---|---|
| `code-reviewer` | Pregled koda: greške, sigurnost, kvalitet (samo čita, ne mijenja) |
| `debugger` | Pronalazi uzrok greške i popravlja je |
| `test-engineer` | Piše unit, integration i e2e testove |
| `refactorer` | Čisti i modernizuje kod bez promjene ponašanja |
| `security-auditor` | Sigurnosni pregled (OWASP, tajni ključevi, zavisnosti) |
| `performance-optimizer` | Ubrzava aplikacije, upite, stranice |
| `frontend-developer` | React, Next.js, TypeScript, Tailwind |
| `backend-architect` | API-ji, baze podataka, arhitektura (Opus) |
| `devops-engineer` | Docker, GitHub Actions, cloud, Kubernetes |
| `ai-engineer` | LLM aplikacije, agenti, RAG, MCP, Claude API (Opus) |
| `docs-writer` | README, dokumentacija, vodiči |

## Dizajn
| Agent | Za šta služi |
|---|---|
| `ui-designer` | Moderan vizuelni dizajn: tipografija, boje, layout, dark mode |
| `ux-designer` | Korisnički tokovi, upotrebljivost, UX tekstovi |
| `design-system-architect` | Design tokeni, teme, biblioteke komponenti |
| `accessibility-auditor` | Pristupačnost po WCAG 2.2 AA |

## Dodavanje novih agenata
Napravi novu `.md` datoteku u `.claude/agents/` sa frontmatterom (`name`, `description`, `tools`, `model`) i uputama ispod.
