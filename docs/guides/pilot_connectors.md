# Review a scoped connector request

[The connector guard](../../pilot/connectors.py) accepts a workspace grant, an action tied to an actor and evidence version, and an approval journal supplied by the integration. Walk through the checks in order. First verify that the credential covers the workspace and operation. Then require enough identifiers to match the reviewed action. The journal consumes the matching independent approval atomically. A missing credential or rejected approval raises `PermissionError` before the action can proceed.

The pilot's local founder service and this connector contract serve different boundaries. A live adapter must implement its journal against a trusted persistent decision store before invoking any outside service.
