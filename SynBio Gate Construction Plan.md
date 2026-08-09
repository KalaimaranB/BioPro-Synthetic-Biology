# BioPro: Synthetic Biology Module
## Logic Gate Construction & Simulation Plan

### Overview
The goal of this module is to bridge the conceptual gap between computer science and biology. Unlike silicon-based digital logic where signals are perfectly isolated and instantaneous, biological logic gates operate in a shared environment (the cytoplasm) and are governed by biochemical kinetics, leakiness, and signal crosstalk. 

This plan outlines a bottom-up approach to building a Synthetic Biology (SynBio) module for BioPro, starting with the fundamental construction of biological logic gates (AND, OR, NOT) before scaling to complex, multi-cellular systems.

---

### Phase 1: The Component Library (Data Model)
Before any visual components are drawn, the foundational biological parts must be defined. Maintaining strict adherence to SOLID principles, this layer will handle data ingestion and abstraction.

* **Objective:** Define genetic parts with their specific chemical properties and kinetic parameters.
* **Implementation:** * Create a core `BiologicalPart` class structure.
    * Integrate with **pySBOL3** to standardize data formats.
    * Build an API hook to the **iGEM Registry of Standard Biological Parts** (or SynBioHub).
* **Key Data Points:** Instead of a generic "Promoter," parts must instantiate with specific properties: binding affinities, transcription/translation rates, degradation rates, and the specific repressor/activator molecules they interact with (e.g., TetR vs. LacI).

### Phase 2: The Orthogonality Checker (Biological Linter)
In a biological circuit, reusing the same protein signal for different gates causes catastrophic crosstalk. The system needs a design rule checker to validate the circuit topology.

* **Objective:** Prevent signal mixing by ensuring all utilized gates are orthogonal.
* **Implementation:**
    * Represent the designed circuit as a directed graph.
    * Utilize **NetworkX** and core data structure traversal algorithms to map signal pathways.
    * If Gate A and Gate C both output the same signaling molecule (e.g., AHL) into the same cellular environment, the UI must flag a visual "Crosstalk Error" and prompt the user to select an orthogonal part.

### Phase 3: The Dynamics Engine (Kinetic Simulation)
Biological computation is time-dependent. A biological AND gate does not instantly output a `1`; it requires time for transcription and translation, and outputs follow a continuous activation curve (Hill equation).

* **Objective:** Simulate the circuit over time, demonstrating real biological phenomena like delay, basal leakiness, and signal thresholds.
* **Implementation:**
    * Translate the validated logic graph into a system of Ordinary Differential Equations (ODEs).
    * Utilize **Tellurium** or **scipy.integrate.odeint** to solve the system dynamically.
    * **Visualization:** Output the simulation as an oscilloscope-style time-series graph, showing the rise and fall of protein concentrations (e.g., tracking fluorescence over time).

### Phase 4: Beyond the Cell (Intercellular Communication)
Once single-cell gates are functioning and successfully simulated, the module can expand to model systems acting outside of a single cell membrane.

* **Objective:** Model spatial dynamics and quorum sensing.
* **Implementation:**
    * Introduce Partial Differential Equations (PDEs) or use an agent-based modeling approach (e.g., **Mesa**).
    * Simulate a signaling molecule (like AHL) diffusing from "Cell 1" across an extracellular grid to activate a receptor on "Cell 2".
    * This sets the stage for modeling population-level logic and advanced synthetic ecosystems.

---

### Immediate Next Steps for Development
1.  **Isolate the Data Model:** Write the Python classes necessary to parse an iGEM XML/JSON part and instantiate it with kinetic parameters.
2.  **Define the Interface:** Establish how a "Wire" in the UI translates into a "Protein Concentration" in the backend solver.
3.  **Prototype the Solver:** Manually hardcode a simple NOT gate (e.g., a TetR repressible promoter) and ensure `scipy` can correctly graph its expected output before building the dynamic drag-and-drop UI.
