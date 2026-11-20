# Use the Windows teaching launcher

[code-map.cmd](../../code-map.cmd) opens the menu. Choose **Learn**, **Teach**, **Sell**, **Files**, **CUDA**, **Verify**, or **Engines**. You can also enter `code-map.cmd teach` directly in a terminal. The launcher works from any current directory. It uses VS Code if it finds `code.cmd` and prints the guide in the terminal otherwise.

Start at the argument checks and follow a mode to its matching label. **Teach** opens the acceptance walkthrough, then runs the synthetic pilot and shows its restored result. **CUDA** starts the screening module with the pinned GPU dependencies and requests CPU parity. Stay in the terminal to see the exit status and results.

Tell the architecture story with the [CTO guide](../CTO_ARCHITECTURE.md). Use the [file map](../code-map.md) to make the story concrete in source and tests.

Run `code-map.cmd engines` to see the inputs and outputs of each [intelligence engine](../architecture/intelligence-engines.md), plus the backlog items for capabilities still under development.

Run `code-map.cmd terms` for the [Machine of Machines terminology](../architecture/system-of-systems.md), architecture views and buyer explanation.

Run `code-map.cmd learning` for the [architecture agent and swarm workflow](../architecture/swarm-learning.md), including how to retrieve a prior lesson.
