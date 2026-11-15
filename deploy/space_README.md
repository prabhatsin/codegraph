---
title: CodeGraph
emoji: 🕸️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# CodeGraph live demo

A context layer for coding agents: it walks a codebase's call graph in HydraDB, so agents get exactly the code they need instead of burning tokens on whole files.

This Space runs HydraDB (official `ghcr.io/hydra-db/hydradb:0.4.0` image) and the CodeGraph UI in one container, loaded with the `rich` repo (100 files) and the calls learned from its own 956-test suite. Every click in Blast radius is a live HydraDB `algo.SSpaths` query.

Source and benchmarks: see the CodeGraph GitHub repository.
