# Resident Evil Companion — MVP Specification

## 1. Purpose

Resident Evil Companion is a personal, unofficial documentation-grounded AI walkthrough and reference assistant for players of the Resident Evil series. The MVP will support one Resident Evil game and one authoritative walkthrough source. The companion will help players who are stuck during gameplay and answer basic Resident Evil questions that are supported by the configured documentation.

This is an independent personal project. It is not affiliated with, endorsed by, sponsored by, or officially connected to Capcom, the Resident Evil franchise, Fandom, or the Resident Evil Wiki community. Resident Evil and related names, characters, and trademarks belong to their respective rights holders. Source material used by the knowledge pipeline should retain appropriate attribution and comply with the applicable source licensing terms.

The MVP is intended to prove the complete knowledge ingestion, synchronization, retrieval, and companion-configuration architecture before expanding to additional games, automated testing, public hosting, or a custom frontend.

## 2. MVP Goals

The MVP must:

- Support one Resident Evil game.
- Use one authoritative Fandom walkthrough as its knowledge source.
- Fetch and process the walkthrough programmatically.
- Split the walkthrough into logical Markdown documents based primarily on physical/progression sections.
- Store the generated Markdown documents in the Git repository.
- Synchronize only new, modified, or deleted documents with Dify.
- Configure the Resident Evil Companion from files in the repository.
- Treat the repository as the single source of truth and Dify as deployed state.
- Use Dify's built-in chat UI as the MVP user interface.
- Use a free/local LLM so the companion has no ongoing model API cost.
- Answer only Resident Evil questions supported by retrieved documentation.
- Ask for clarification when a user's question does not contain enough game/version/context information.
- Refuse unsupported or out-of-scope questions rather than hallucinating.

## 3. Non-Goals for the MVP

The following are intentionally deferred:

- Supporting the entire Resident Evil franchise.
- Automated evaluation/test cases.
- GitHub Actions and scheduled documentation refreshes.
- Automatic CI/CD deployment.
- Public hosting.
- A React, Next.js, or other custom frontend.
- Sophisticated rename detection.
- Multiple walkthrough/reference sources per game.
- Lore coverage beyond what the selected walkthrough supports.
- Automatic fallback to the LLM's pretrained Resident Evil knowledge.

## 4. High-Level Architecture

```text
Resident Evil Fandom Walkthrough
              |
              v
     fetch_walkthrough.py
              |
              v
 Parse walkthrough structure
              |
              v
knowledge/resident-evil-<game>/
├── mansion.md
├── guardhouse.md
├── mansion-return.md
├── caves.md
└── laboratory.md
              |
              v
         sync_dify.py
              |
              v
      Dify Knowledge Base
              |
              v
   Resident Evil Companion
              |
              v
      Dify Built-in Chat UI
              |
              v
            User
```

The Git repository is the canonical representation of the companion. Dify is the deployed representation of that state.

## 5. Repository Structure

Initial target structure:

```text
resident-evil-companion/
├── config/
│   └── companion.yaml
├── knowledge/
│   └── resident-evil-1996/
│       ├── mansion.md
│       ├── guardhouse.md
│       ├── mansion-return.md
│       ├── caves.md
│       └── laboratory.md
├── prompts/
│   └── system_prompt.md
├── scripts/
│   ├── fetch_walkthrough.py
│   └── sync_dify.py
├── .env.example
├── .gitignore
├── README.md
└── spec.md
```

The exact generated section names may differ according to the structure of the authoritative walkthrough.

## 6. Knowledge Source

For the first MVP, a single Resident Evil Fandom walkthrough will be the authoritative source.

Initial source:

`Walkthrough: Resident Evil`

The companion must not assume that it has information beyond this source. If the walkthrough does not contain enough information to answer a question, the companion must say that it cannot answer the question with the information currently available.

The pipeline should preserve source attribution as appropriate when transforming source content into Markdown.

## 7. Documentation Ingestion

### 7.1 `fetch_walkthrough.py`

This script is responsible only for obtaining and processing documentation. It should not contain Dify-specific synchronization logic.

Responsibilities:

1. Retrieve the configured walkthrough from Fandom/MediaWiki.
2. Parse the walkthrough's heading hierarchy.
3. Identify major walkthrough/progression sections automatically.
4. Remove irrelevant webpage/wiki presentation content where appropriate.
5. Preserve useful headings and character-specific instructions.
6. Convert the relevant content into clean Markdown.
7. Generate one Markdown file per major walkthrough section.
8. Automatically overwrite the existing generated Markdown files when the source changes.
9. Clearly log when the fetch completes and whether documentation changed.

The pipeline should trust the latest structure of the authoritative walkthrough for the MVP.

### 7.2 Document Organization

Documents should primarily be organized around physical locations/progression sections.

Example:

```text
knowledge/resident-evil-1996/
├── mansion.md
├── guardhouse.md
├── mansion-return.md
├── caves.md
└── laboratory.md
```

Character-route differences should remain inline in the relevant location document rather than duplicating complete Jill and Chris walkthroughs.

Example:

```markdown
## Shotgun

### Jill
...

### Chris
...
```

If a generated location document contains information for both characters, its document-level character metadata will be `both`.

## 8. Git and Knowledge Versioning

Generated Markdown knowledge files are committed to Git.

This means the repository stores:

- The pipeline used to create the documentation.
- The exact documentation currently intended for deployment.
- Historical versions of that documentation through Git history.

For the MVP, running the fetch script is manual. The developer reviews/commits/pushes the resulting repository changes manually.

GitHub Actions and scheduled Fandom refreshes are deferred.

## 9. Dify Knowledge Base

The MVP uses a Dify knowledge base for retrieval.

For the first game, only that game's documents will exist. The longer-term architecture should support a single large Resident Evil knowledge base containing multiple games, using metadata filtering to prevent cross-game retrieval.

Future conceptual structure:

```text
Resident Evil Knowledge Base
├── Resident Evil (1996) documents
├── Resident Evil 2 documents
├── Resident Evil 3 documents
└── ...
```

Game isolation will be achieved through document metadata rather than separate knowledge bases per game.

## 10. Document Metadata

`sync_dify.py` is responsible for generating Dify document metadata.

Required metadata fields:

```text
sha256
source_path
game
version
section
character
```

Example:

```text
sha256: <calculated SHA-256>
source_path: resident-evil-1996/mansion.md
game: resident-evil
version: 1996
section: mansion
character: both
```

Metadata serves two purposes:

1. Synchronization (`sha256`, `source_path`).
2. Retrieval filtering (`game`, `version`, `section`, `character`).

The sync script should derive metadata from the repository/file structure wherever practical rather than requiring duplicated metadata inside each Markdown document.

If Dify's custom metadata APIs cannot cleanly support the synchronization fields required by the implementation, a manifest-based fallback may be considered. A manifest should not be exposed to normal RAG retrieval if avoidable.

## 11. Dify Synchronization

### 11.1 `sync_dify.py`

This script is responsible for synchronizing repository state with Dify.

It should:

1. Enumerate local Markdown knowledge files.
2. Calculate a SHA-256 hash for each file.
3. Retrieve the corresponding Dify documents and metadata.
4. Compare local state with deployed state.
5. Create new documents.
6. Update modified documents.
7. Skip unchanged documents.
8. Delete Dify documents that no longer exist locally.
9. Update document metadata after successful synchronization.
10. Configure/synchronize the companion itself from repository configuration.

### 11.2 Change Behavior

```text
Local state              Dify action
---------------------------------------------
New file                 Create document
Same path, changed hash  Update document
Same path, same hash     Skip
Missing local file       Delete document
Renamed file             Delete old + create new
```

For the MVP, the file's relative path is its identity.

True rename detection is deferred. A rename is treated as deletion of the old path and creation of the new path.

No separate local `sync-state.json` should be required if Dify metadata can act as the remote synchronization state.

### 11.3 Failure Behavior

Synchronization should not intentionally leave the user-facing knowledge base in a partially updated state.

The desired behavior is all-or-nothing from the companion user's perspective: if synchronization fails, the existing Dify deployment should remain at the previous known-good state.

The exact transaction/versioning strategy required to achieve this will be determined after validating Dify's available APIs.

## 12. Companion as Code

The Resident Evil Companion must be configured from the repository rather than manually configured only through Dify's UI.

Proposed configuration:

```text
config/companion.yaml
prompts/system_prompt.md
```

`companion.yaml` should eventually represent configurable deployment settings such as:

- Companion/app name.
- Model/provider selection.
- Knowledge base association.
- Retrieval configuration.
- Relevant generation/model parameters.
- Other Dify app settings that are available through supported APIs.

`system_prompt.md` contains the companion's behavioral instructions.

The repository is the single source of truth. Manual changes made in Dify are considered configuration drift and may be overwritten on the next synchronization.

A technical implementation risk remains: Dify's APIs must be verified to determine which companion configuration fields can actually be created/updated programmatically.

## 13. Companion Behavior

The companion's primary job is to act as a conversational walkthrough and Resident Evil reference assistant.

### 13.1 Grounding

The companion must answer using retrieved documentation only.

It must not fill missing information using the underlying model's pretrained Resident Evil knowledge.

If sufficient supporting documentation is not retrieved, it should respond formally that it cannot answer the question with the information currently available.

### 13.2 Scope

The companion only answers Resident Evil-related questions.

For an unrelated question, it should:

1. Politely refuse the request.
2. Remind the user that it is designed to answer Resident Evil questions.

### 13.3 Clarification

The companion should use as much context as the user provides.

Relevant context may include:

- Game.
- Original/remake/version.
- Character/route.
- Current location.
- Items held.
- Most recently completed objective/event.

The companion should not mechanically ask for every field when enough context is already available.

If the game/version is ambiguous or there is insufficient context to safely retrieve the correct walkthrough information, the companion should ask a clarifying question before retrieval rather than search broadly and risk returning information from the wrong game/version.

## 14. Model and Cost Constraints

The MVP must have no ongoing paid model API cost.

The intended architecture is:

```text
Dify
  |
  v
Local model provider
  |
  v
Ollama (or equivalent)
  |
  v
Open-source LLM
```

The exact local model is not part of the initial architecture decision and can be selected based on local hardware performance and its ability to follow grounding instructions reliably.

No OpenAI/Anthropic/etc. paid API is required for the MVP.

## 15. User Interface

Dify's built-in chat/debug UI is the only frontend required for the MVP.

No custom frontend is required.

Dify may run locally/self-hosted for the MVP. The companion should still be visible, configurable, and usable through the local Dify web interface.

Public internet access is deferred.

## 16. Manual MVP Workflow

For the first game, the development workflow is intentionally manual:

```text
1. Run fetch_walkthrough.py
          |
          v
2. Inspect generated knowledge/*.md
          |
          v
3. Commit/push desired changes to Git
          |
          v
4. Run sync_dify.py
          |
          v
5. Verify KB/documents/configuration in Dify
          |
          v
6. Ask grounded questions through Dify UI
```

Automation is added only after this workflow is reliable.

## 17. MVP Definition of Done

The MVP is complete when all of the following are true:

- One Resident Evil walkthrough can be fetched programmatically.
- The walkthrough is automatically divided into logical Markdown documents.
- Those Markdown files are stored and versioned in the repository.
- A Dify knowledge base can be created/configured for the project.
- `sync_dify.py` can create, update, skip, and delete documents based on repository state.
- SHA-256-based change detection works for modified files.
- Required synchronization/retrieval metadata is associated with Dify documents.
- The Resident Evil Companion is configured from repository files.
- Repository configuration is visibly represented in Dify.
- The Companion uses the synchronized knowledge base.
- The Companion can be used through Dify's built-in UI.
- The Companion asks for clarification when necessary.
- The Companion refuses non-Resident-Evil questions appropriately.
- The Companion does not intentionally answer unsupported questions from model memory.
- The system runs using a free/local model without paid per-token API usage.

Automated test cases are not required to declare this first MVP complete.

## 18. Post-MVP Roadmap

After the first MVP works end-to-end, likely follow-up phases include:

### Phase 2 — Evaluation
- Create representative gameplay questions.
- Add expected-answer/retrieval criteria.
- Build automated regression tests.
- Evaluate hallucination and grounding behavior.

### Phase 3 — Additional Games
- Add walkthrough sources game-by-game.
- Expand metadata filtering across games and versions.
- Verify that retrieval cannot confuse originals and remakes.

### Phase 4 — Automation
- Add GitHub Actions.
- Periodically refresh Fandom documentation.
- Log `No documentation changes detected` when appropriate.
- Automatically synchronize Dify when knowledge/configuration changes.
- Fail deployments safely when synchronization cannot complete.

### Phase 5 — Product Expansion
- Consider additional authoritative Resident Evil reference sources.
- Expand supported question types.
- Consider public hosting.
- Consider a custom frontend if Dify's built-in UI becomes limiting.

## 19. Open Technical Questions

These should be resolved during implementation rather than assumed:

- Which Dify APIs expose all required app/companion configuration settings?
- Can Dify custom document metadata cleanly store and return `sha256` and `source_path` for synchronization?
- What is the safest way to provide all-or-nothing knowledge deployments with Dify's available APIs?
- What Dify retrieval configuration best supports future metadata filtering across games?
- Which local model provides acceptable instruction-following and grounded-answer quality on the development machine?
- What exact Fandom/MediaWiki representation is easiest to transform reliably into clean Markdown sections?

## 20. Guiding Principle

Keep the first version narrow.

The MVP exists to prove this chain reliably:

```text
Authoritative walkthrough
        ->
Version-controlled structured knowledge
        ->
Incremental Dify synchronization
        ->
Configuration-as-code companion
        ->
Grounded Resident Evil answers
```

Additional games, automated testing, CI/CD, richer sources, and custom interfaces should only be added after that chain works end-to-end.
