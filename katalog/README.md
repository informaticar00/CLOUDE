# Katalog agenata i skillova

Pregled svih agenata i skillova u ovom repozitoriju, složenih po kategorijama.

Ovo je samo popis. Sami agenti i skillovi moraju ostati u `.claude/agents/` i `.claude/skills/`, jer ih Claude Code učitava samo odande.

## Kako se koriste
- **Agenti** su specijalisti kojima Claude predaje dio posla. Claude ih bira sam prema zadatku, a možeš ih tražiti i po imenu: *"Koristi code-reviewer agenta da pregleda moje izmjene."*
- **Skillovi** su upute za određenu vrstu posla. Claude ih uključuje sam kad prepozna zadatak, a pokrećeš ih i sa `/ime-skilla`, npr. `/caveman` ili `/brainstorming`.

## Kategorije

| Kategorija | Agenti | Skillovi |
|---|---|---|
| [Planiranje i ideje](01-planiranje-i-ideje.md) | 2 | 11 |
| [Programiranje i arhitektura](02-programiranje-i-arhitektura.md) | 14 | 13 |
| [Testiranje i debugiranje](03-testiranje-i-debugiranje.md) | 4 | 4 |
| [Code review i kvaliteta](04-code-review-i-kvaliteta.md) | 4 | 7 |
| [Git, DevOps i objava](05-git-devops-i-objava.md) | 5 | 12 |
| [Dizajn i UI](06-dizajn-i-ui.md) | 4 | 8 |
| [AI i agenti](07-ai-i-agenti.md) | 4 | 4 |
| [Pisanje i dokumentacija](08-pisanje-i-dokumentacija.md) | 4 | 10 |
| [Video i prezentacije](09-video-i-prezentacije.md) | 0 | 14 |
| [Štednja tokena](10-stednja-tokena.md) | 0 | 5 |
| [Alati i snalaženje](11-alati-i-snalazenje.md) | 0 | 5 |
| [Marketing i prodaja](12-marketing.md) | 0 | 28 |
| [SEO](13-seo.md) | 0 | 26 |
| [Oglašavanje](14-oglasavanje.md) | 0 | 34 |
| [Blog](15-blog.md) | 0 | 33 |
| [Compound Engineering](16-compound-engineering.md) | 0 | 35 |
| **Ukupno** | **41** | **249** |

## Izvori
- Agenti: vlastiti te iz [VoltAgent/awesome-claude-code-subagents](https://github.com/VoltAgent/awesome-claude-code-subagents) i [wshobson/agents](https://github.com/wshobson/agents) (MIT, vidi [THIRD_PARTY_AGENTS.md](../.claude/THIRD_PARTY_AGENTS.md)).
- Skillovi: [obra/superpowers](https://github.com/obra/superpowers), [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), [mattpocock/skills](https://github.com/mattpocock/skills), [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman), [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail), [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill), [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes), [anthropics/skills](https://github.com/anthropics/skills), [blader/humanizer](https://github.com/blader/humanizer), [PleasePrompto/notebooklm-skill](https://github.com/PleasePrompto/notebooklm-skill), [garrytan/gstack](https://github.com/garrytan/gstack), [vercel-labs/skills](https://github.com/vercel-labs/skills), [pbakaus/impeccable](https://github.com/pbakaus/impeccable), [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), [emilkowalski/skill](https://github.com/emilkowalski/skill), [mvanhorn/last30days-skill](https://github.com/mvanhorn/last30days-skill), [remotion-dev/skills](https://github.com/remotion-dev/skills), [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills), [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills), [AgriciDaniel/claude-seo](https://github.com/AgriciDaniel/claude-seo), [AgriciDaniel/claude-ads](https://github.com/AgriciDaniel/claude-ads), [AgriciDaniel/claude-blog](https://github.com/AgriciDaniel/claude-blog), [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills), [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin). Točne verzije su u [skills-lock.json](../skills-lock.json).

## Dodavanje novog skilla
```bash
npx skills add <vlasnik/repo> --skill <ime> -a claude-code -y
```
Zatim ga upiši u odgovarajuću kategoriju ovdje.
