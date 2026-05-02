# Network Door, BYOM, and Native Assistant operator events

AgentTerm is the operator-visible ChatOps surface for SourceOS work. The first Network Door / BYOM / Native Assistant integration slice uses existing AgentTerm event recording rather than invoking network, firewall, model-provider, or native assistant adapters directly.

This keeps AgentTerm aligned with AgentPlane evidence contracts:

- `NetworkDoorPlanEvidence`
- `ExternalModelProviderRouteEvidence`
- `NativeAssistantBridgeEvidence`

## Operator event commands

Network Door plan event:

```bash
agent-term record agentplane network_door_plan '!sourceos-network' \
  'Plan enterprise/user network route for models.enterprise.example' \
  --requires-approval \
  --metadata-json '{"networkAccessProfileRef":"urn:srcos:network-access-profile:enterprise-and-user-default","evidenceKind":"NetworkDoorPlanEvidence","delegatedExecutor":"sourceosctl network plan"}'
```

BYOM / external model provider event:

```bash
agent-term record agentplane external_model_provider_route '!sourceos-network' \
  'Plan BYOM OpenAI-compatible provider route' \
  --requires-approval \
  --metadata-json '{"providerRef":"urn:srcos:external-model-provider-profile:user-openai-compatible","evidenceKind":"ExternalModelProviderRouteEvidence","delegatedExecutor":"sourceosctl network provider"}'
```

Native assistant bridge event:

```bash
agent-term record agentplane native_assistant_bridge '!sourceos-native' \
  'Plan Apple App Intents bridge for Office artifact creation' \
  --requires-approval \
  --metadata-json '{"bridgeRef":"urn:srcos:native-assistant-bridge-profile:apple-app-intents-default","evidenceKind":"NativeAssistantBridgeEvidence","delegatedExecutor":"sourceosctl native-assistant plan"}'
```

## Boundary

AgentTerm records operator intent and policy posture. It does not:

- mutate firewall state;
- install or configure service mesh components;
- contact BYOM or enterprise model providers;
- store provider credentials;
- invoke Siri, Apple App Intents, Shortcuts, Android intents, Windows shell APIs, browser extensions, MCP/native transports, or other native assistant APIs;
- send prompt text or destination text;
- bypass Policy Fabric.

## Event ownership

| Event kind | Owning evidence contract | Delegated local plan surface |
|---|---|---|
| `network_door_plan` | `NetworkDoorPlanEvidence` | `sourceosctl network plan` |
| `external_model_provider_route` | `ExternalModelProviderRouteEvidence` | `sourceosctl network provider` |
| `native_assistant_bridge` | `NativeAssistantBridgeEvidence` | `sourceosctl native-assistant plan` |

## Future slash command surface

The future interactive shell should map these to:

```text
/network plan <destination>
/byom provider <profile-ref>
/native-assistant plan <operation>
```

Until those dedicated shell commands exist, `agent-term record ...` is the supported operator-visible event path.
