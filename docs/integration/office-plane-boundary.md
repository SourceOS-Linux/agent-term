# Prophet Workspace Office Plane boundary

AgentTerm exposes operator-facing Office Plane commands for workroom-bound office artifacts.

AgentTerm does **not** generate documents, convert files, invoke LibreOffice, operate Collabora/ONLYOFFICE, or send mail directly. It records governance-preserving intent events and delegates execution/evidence to the owning planes.

## Command surface

Top-level CLI events:

```bash
agent-term office create-doc '!prophet-workspace' --workroom workroom-demo-0001 --title 'Demo Report'
agent-term office create-sheet '!prophet-workspace' --workroom workroom-demo-0001 --title 'Demo Workbook'
agent-term office create-deck '!prophet-workspace' --workroom workroom-demo-0001 --title 'Demo Briefing Deck'
agent-term office convert '!prophet-workspace' /workspace/output/demo.docx --to pdf --workroom workroom-demo-0001
agent-term office inspect '!prophet-workspace' /workspace/output/demo.pptx --workroom workroom-demo-0001
agent-term office evidence '!prophet-workspace' /workspace/evidence/office.json --workroom workroom-demo-0001
```

Interactive shell commands:

```text
/office create-doc <title>
/office create-sheet <title>
/office create-deck <title>
/office convert <path> <format>
/office inspect <path>
```

## Event model

All Office commands record `prophet-workspace` events with kind:

```text
office_artifact_request
```

Event metadata includes:

- workroom id;
- operation;
- OfficeArtifact schema ref;
- expected AgentPlane evidence kind;
- delegated `sourceosctl office ...` command shape;
- policy posture.

## Responsibility split

| Plane | Responsibility |
|---|---|
| AgentTerm | Operator command/event surface and Matrix-first ChatOps history. |
| Prophet Workspace | Professional Workroom and OfficeArtifact product semantics. |
| sourceosctl | Local Office dry-run and future execution adapter. |
| AgentPlane | OfficeArtifactEvidence and run/evidence/replay lineage. |
| Policy Fabric | Side-effect approval for send/publish/calendar modifications. |
| Agent Registry | Non-human agent identity and tool grants. |

## Approval posture

Office generation and conversion are approval-required in AgentTerm because they can lead to persisted artifacts or external sharing.

Office inspection and evidence inspection are read-only and do not require approval by default.

Sending email, publishing externally, or modifying calendars is not implemented here and must remain policy-gated side-effect flow in future slices.

## Backend posture

AgentTerm does not care whether an Office artifact is eventually produced by LibreOffice, Collabora, ONLYOFFICE, Microsoft Graph, Google Workspace, or SourceOS-native tooling. Backend selection belongs to Prophet Workspace and the delegated execution surface.
