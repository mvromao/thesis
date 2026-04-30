# Plan: Structure Your 4G Network Appendix

**TL;DR**: Build the appendix in three phases: (1) System architecture overview with visual modular diagram, (2) detailed step-by-step deployment (hardware setup, network configuration, hurdles), and (3) validation and results. This flow takes readers from "what does the system look like?" → "how do we build it?" → "does it work?"

---

## Phase 1: Architecture & System Overview *(Write First)*

Present what your 4G system is before diving into implementation details.

### Section: System Architecture Overview
- Brief intro: Explain that this appendix documents the 4G testbed as a pre-study/baseline for 5G development
- State scope: What you built (e.g., "LTE testbed with Open5GS core and srsLTE RAN") 

### Section: Modular Architecture *(with main diagram)*
- Create/include primary architecture diagram showing:
  - The two machines and their roles
  - Main modules: RAN (gNB), Core (EPC/AMF/SMF/UPF/PGW), Testbed UE, Backhaul/Management
  - Data and control plane connections
  - Insert as figure with clear labels
- Describe each module in 2-3 sentences: What does it do? What software runs on it?

### Section: Module Interactions & Network Flow
- Sub-section for each critical interaction:
  - *RAN-to-Core*: What messages/protocols connect them
  - *Core-to-UE*: Data plane path
  - *Management*: How you monitor/configure
- Include supplementary diagrams here if helpful (protocol stack, message flow)

---

## Phase 2: Implementation & Deployment *(Write Second)*

Walk through how you actually built it, including the hurdles.

### Section: Hardware Setup
- Expand existing Hardware Components table ✓ (already written)
- Add subsection: *Ethernet Connectivity & Physical Layout*
  - Describe: How machines connect (ethernet cable specs, network ports used)
  - **Hurdle #1**: Physical cable requirements, port configuration
  - Diagram: Simple physical topology (if not in Phase 1)

### Section: Network Interface Configuration
- Document network interfaces on both machines
- IP addressing scheme (e.g., backhaul network 10.x.x.x, management network)
- **Hurdle #2**: Linux network interface setup (NIC naming, static IPs, firewall rules)
- Include: command examples or config snippets for reproducibility

### Section: Software Stack & Deployment
- Software components on each machine:
  - *Machine 1*: Core functions (list which network functions: AMF, SMF, UPF, PGW, etc. with brief role)
  - *Machine 2*: RAN and/or testbed UE
- **Hurdle #3**: Any synchronization, time sync, library dependencies, build issues
- Briefly mention: version constraints, compatibility notes

### Section: Core Network Functions *(subsection or separate)*
- Describe the network functions deployed in your core:
  - What each function does (1-2 sentences each)
  - Configuration parameters that matter (e.g., IP pools, PLMN ID, APN setup)
  - How they interact with each other

### Section: CPU Governor & Performance Tuning
- Reference your CPU governor script here
- Explain: Why this matters for 4G testbed (low latency, consistent performance)
- Include: Script snippet showing key settings (governor mode, frequency scaling)

---

## Phase 3: Validation & Results *(Write Last)*

Demonstrate the system works.

### Section: Testing Methodology
- What you tested (throughput? latency? connection establishment?)
- How you measured (tools, duration, number of runs)

### Section: Test Results
- Present key metrics in tables or graphs:
  - Throughput, latency, reliability, handover success rate, etc.
- Interpret: What these results tell you about the 4G baseline
- Bridge to 5G: "These results serve as baseline for 5G comparison"

---

## Relevant Files

- [3-BackMatter/appendix1.tex](3-BackMatter/appendix1.tex) — Current appendix (Hardware section exists; expand from here)
- [2-MainMatter/3 - Workplan.tex](2-MainMatter/3%20-%20Workplan.tex) — Reference for network function details (AMF, SMF, UPF, PCF)
- [5-Figures/](5-Figures/) — Use DrawIO diagrams as templates or reference for architecture diagrams

---

## Verification

1. **Structure check**: Does each reader understand: (a) what the system looks like, (b) how it was built, (c) that it works?
2. **Section completeness**: Each main section (Phases 1–3) should have at least one diagram/table
3. **Reproducibility**: Could someone follow the setup steps and replicate your network?
4. **Clarity on hurdles**: Are all critical obstacles (ethernet, network interfaces, config issues) clearly explained as learning points?
5. **Bridge to 5G**: Concluding paragraph should tie this back to why 4G setup matters for 5G development

---

## Detailed Checklist (Step-by-Step)

### Pre-Writing ☐
- [ ] List all modules in your exact setup (RAN, Core, UE, Management)
- [ ] Gather network function list (from Open5GS or equivalent core)
- [ ] Locate test results file
- [ ] Locate CPU governor script file
- [ ] List all hurdles/blockers you encountered (network config, sync issues, dependencies, etc.)

### Phase 1: Architecture ☐
- [ ] Write intro paragraph (scope, purpose, software stack name)
- [ ] Create main architecture diagram (or adapt from existing drawio)
- [ ] Write 2–3 sentence description of each module
- [ ] Write module interaction section (how data flows between components)
- [ ] Add supplementary diagram(s) if needed (protocol stack, physical layout)

### Phase 2: Implementation ☐
- [ ] Verify/expand Hardware Components section
- [ ] Write Physical Connectivity subsection (ethernet specs, ports, **Hurdle #1**)
- [ ] Document network interface setup (IPs, naming, **Hurdle #2**)
- [ ] List software stack per machine
- [ ] Note any deployment hurdles encountered (**Hurdle #3**: build issues, sync, dependencies)
- [ ] Write Network Functions section (list functions, roles, key configs)
- [ ] Integrate CPU Governor script with explanation section

### Phase 3: Validation ☐
- [ ] Write Testing Methodology section (what, how, tools)
- [ ] Insert test results (tables/graphs)
- [ ] Interpret results briefly
- [ ] Write concluding bridge: why this 4G baseline matters for 5G

### Final Polish ☐
- [ ] Cross-check all figure references and captions
- [ ] Verify acronyms are defined (or use `\gls{}` macros)
- [ ] Spell-check and consistency check (consistent terminology across sections)
- [ ] Ensure citations/references to tools (Open5GS, srsLTE, etc.) are accurate
- [ ] Proofread for LaTeX compile errors

---

## Key Decisions

- **Scope**: This appendix is *4G only* — it serves as a baseline and reference for 5G work documented in main chapters. Keep 5G comparisons minimal here.
- **Level of detail**: Include enough detail that someone could replicate the setup, but don't over-detail every config file. Focus on critical decisions and hurdles.
- **Figures**: One main architecture diagram is primary; supplementary diagrams (physical, protocol stack) support specific sections.
- **Audience**: Your thesis readers (likely professors and researchers in networking) — assume they understand 4G concepts but may not know your exact testbed configuration.
