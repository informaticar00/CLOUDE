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

## Popularni agenti sa GitHuba
Preuzeti iz `VoltAgent/awesome-claude-code-subagents` i `wshobson/agents` (MIT licenca, vidi `THIRD_PARTY_AGENTS.md`).

### Jezici i frameworci
| Agent | Za šta služi |
|---|---|
| `typescript-pro` | Napredni TypeScript, tipovi, generici |
| `python-pro` | Moderni Python, async, tipovi |
| `golang-pro` | Go, konkurentnost, mikroservisi |
| `rust-engineer` | Rust, sigurnost memorije, performanse |
| `react-specialist` | Napredni React 19, Server Components |
| `nextjs-developer` | Next.js App Router, SSR/SSG, SEO |
| `fullstack-developer` | Kompletne funkcionalnosti od baze do UI-ja |
| `mobile-developer` | React Native / Flutter mobilne aplikacije |

### Backend, podaci i infrastruktura
| Agent | Za šta služi |
|---|---|
| `api-designer` | Dizajn REST/GraphQL API-ja |
| `postgres-pro` | PostgreSQL optimizacija i administracija |
| `kubernetes-specialist` | Kubernetes klasteri i deploy |
| `terraform-engineer` | Infrastruktura kao kod |
| `sre-engineer` | Pouzdanost, SLO, monitoring |
| `git-workflow-manager` | Git strategije grana i workflow |

### AI
| Agent | Za šta služi |
|---|---|
| `llm-architect` | Arhitektura LLM sistema, RAG, fine-tuning |
| `prompt-engineer` | Pisanje i optimizacija promptova |
| `mcp-developer` | Pravljenje MCP servera i klijenata |

### Kvalitet i sigurnost
| Agent | Za šta služi |
|---|---|
| `tdd-orchestrator` | Test-driven development (red-green-refactor) |
| `threat-modeling-expert` | Modeliranje prijetnji (STRIDE) |

### Dizajn, proizvod i dokumentacija
| Agent | Za šta služi |
|---|---|
| `ui-ux-designer` | Wireframeovi, dizajn sistemi, inkluzivni dizajn |
| `ui-visual-validator` | Vizuelna provjera UI-ja na screenshotima |
| `ux-researcher` | Istraživanje korisnika |
| `product-manager` | Strategija proizvoda, prioriteti, roadmap |
| `seo-specialist` | SEO optimizacija |
| `docs-architect` | Opsežna tehnička dokumentacija iz koda |
| `mermaid-expert` | Dijagrami (flowchart, sekvence, ERD) |

## Dodavanje novih agenata
Napravi novu `.md` datoteku u `.claude/agents/` sa frontmatterom (`name`, `description`, `tools`, `model`) i uputama ispod.
