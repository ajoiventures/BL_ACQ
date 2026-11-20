// Every item here is fictional and safe to serve from a local static server.
// A workflow lists its allowed event transitions in order. The UI derives the next action from this list.
export const modules = [
  "Command",
  "World Map",
  "Acquisitions",
  "Capital",
  "Documents",
  "Operations",
  "Network",
  "Family Office",
  "Agents",
  "System",
];
export const workflows = {
  parcel: {
    title: "Orchard parcel",
    scope: "commercial",
    module: "Acquisitions",
    source: "Synthetic parcel and comparable-sales packet",
    version: "parcel-v1",
    steps: [
      "Select parcel",
      "Record underwriting",
      "Approve simulated bid review",
    ],
  },
  intake: {
    title: "Incoming project brief",
    scope: "commercial",
    module: "Documents",
    source: "Synthetic inbox message and attached brief",
    version: "brief-v1",
    steps: [
      "Ingest sample message",
      "Review extracted document",
      "Create review task",
    ],
  },
  settlement: {
    title: "Service invoice",
    scope: "commercial",
    module: "Capital",
    source: "Synthetic invoice and separate receipt fixture",
    version: "receipt-v1",
    steps: [
      "Review invoice",
      "Attach settlement receipt",
      "Reconcile simulated receipt",
    ],
  },
  maintenance: {
    title: "Pump maintenance",
    scope: "family",
    module: "Operations",
    source: "Synthetic maintenance request and vendor estimate",
    version: "pump-v1",
    steps: ["Review request", "Review estimate", "Approve simulated dispatch"],
  },
  district: {
    title: "District field note",
    scope: "civic",
    module: "World Map",
    source: "Synthetic public-space observation",
    version: "civic-v1",
    steps: ["Review field note", "Record evidence"],
  },
};
export const coverage = [
  [
    "Parcel selection to underwriting and approval",
    "parcel",
    "Guided workflow",
  ],
  ["Inbox message to document and review task", "intake", "Guided workflow"],
  [
    "Maintenance request to dispatch decision",
    "maintenance",
    "Guided workflow",
  ],
  ["Invoice to settlement and reconciliation", "settlement", "Guided workflow"],
  ["District observation to cited record", "district", "Guided workflow"],
  ["Evidence version inspection", "Command", "Local capability"],
  [
    "Missing funding evidence to review hold",
    "Acquisitions",
    "Local capability",
  ],
  ["Draft to second-device handoff", "Command", "Manual JSON transfer"],
  ["Workspace switch and checkpoint resume", "Command", "Local capability"],
  ["Reviewer activity trace", "Agents", "Scoped local history"],
  ["Contact relationship lookup", "Network", "Future service"],
  ["System health and connector inventory", "System", "Local status only"],
];
