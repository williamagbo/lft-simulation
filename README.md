# Liver Function Test (LFT) Laboratory Simulation App

An interactive, data-driven web application built with **Streamlit** and powered by **SimPy** to model, simulate, and optimize operational efficiency and workflow dynamics within a healthcare laboratory setting. 

The application utilizes discrete-event simulation (DES) and prescriptive analytics to identify operational bottlenecks, evaluate resource utilization, and optimize Turnaround Time (TAT) metrics.

🔗 **Live Application:** [lftsimulation.streamlit.app](https://lftsimulation.streamlit.app/)

---

## 🚀 Features

* **Interactive DES Simulation:** Tweak staffing levels, equipment capacities, and arrival rates using a robust SimPy backend to see immediate operational impacts.
* **Prescriptive Analytics Engine:** Optimize resource allocation dynamically based on target SLAs and budget constraints.
* **Queueing Theory & Insights:** Compare real-world simulation outputs side-by-side with mathematical queueing models.
* **Exploratory Data Analysis:** Built-in charts and density plots visualizing processing times, bottleneck areas, and laboratory performance metrics.

---

## 📂 Repository Structure

The repository is structured as a modular Streamlit multi-page application:

```text
├── app.py                      # Main entry point for the Streamlit application
├── simulation_engine.py         # Core SimPy Discrete-Event Simulation engine
├── data_utils.py               # Data processing and analytics utility functions
├── lft_records.csv             # Baseline laboratory operational data
├── requirements.txt            # Python dependencies
├── data/
│   └── lft_records.csv         # Project data storage
└── pages/                      # Multi-page application modules
    ├── 1_About.py              # Project background and context
    ├── 2_How_To_Guide.py       # Application user documentation
    ├── 3_Queuing_Theory.py     # Mathematical framework modeling
    ├── 4_DES_Simulation.py     # Interactive SimPy configuration dashboard
    ├── 5_Optimizer.py          # Operational optimization and prescriptive modeling
    └── 6_Data_Analysis.py      # Historical data analysis and visualizations