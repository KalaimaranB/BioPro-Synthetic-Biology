# Feature Specification: Literature Context Importer

## Overview
In synthetic biology, kinetic parameters (y_max, K_d, etc.) are meaningless without their experimental context. If a user combines parts characterized under different conditions (e.g., *E. coli* DH10B in LB vs. *E. coli* MG1655 in M9 minimal media), the simulation will fail to reflect reality.

This feature introduces a **Literature Importer & Comparison Engine** that shifts the responsibility of data validation to the researcher, empowering them to make informed decisions rather than relying on black-box assumptions.

## Core Workflows

### 1. Literature Import
Instead of just typing numbers into a vacuum, researchers create "Parameter Profiles" tied directly to published literature.
* **DOI Fetching:** The user inputs a DOI or PMID. BioPro queries an API (e.g., EuropePMC) to pull the paper's title, authors, and abstract.
* **Manual Data Logging:** The researcher reads the paper and manually inputs the kinetic parameters along with mandatory context metadata:
  * **Host Strain** (e.g., *E. coli* DH10B)
  * **Media** (e.g., M9, LB)
  * **Temperature** (e.g., 37°C)
  * **Plasmid Backbone / Copy Number** (e.g., p15A, ColE1)
  * **Inducer concentrations** (if applicable)

### 2. The Context Comparison Engine (Manual Approval)
When a user drags two parts onto the Canvas that have parameters sourced from different papers, BioPro will **not** automatically assume they are compatible.
* **The Flag:** The UI will flag the connection with a "Context Mismatch" warning icon.
* **Side-by-Side Review:** Clicking the warning opens a comparison window showing the experimental context of Paper A next to Paper B.
* **Researcher Approval:** The software defers to the researcher's expertise. The researcher must review the differences and explicitly click **"Approve Compatibility"** to allow the simulation engine to combine the math. 

> [!NOTE]
> This ensures that all simulations are built on rigorous, researcher-verified assumptions rather than hidden software defaults.
