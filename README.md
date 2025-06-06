# InfiniteVibe Media Production and Streaming

InfiniteVibe is an AI‐driven video and media studio putting Bittensor at the frontier of AI-Generated video production. 

Miners respond to tasks and create AI-generated videos using any model or means at their own disposal. Miner scoring and emissions are determined by real world user feedback e.g. paying for the SN output or views/engagement. As a way to grow awareness and attract the world's best creatives to SN89, the SN will first reward miners based on submissions engagement on the miner's own social media profiles. We will funnel traffic to infinitevibe.ai and tensorflix.ai - where a Beta list of organic tasks is being populated waiting for the SN reach quality output.

Validators act as editor/producers, ensuring that miner quality progresses to the highest levels. 

Our goal is to align Validators and Miners closely with the quality of the SN product. As such Miners and Validators will be incentivized to hold Alpha either as collateral or stakeweight - and jointly benefit from monetization of the platform.  

## Creative Direction

We will give miners full creative freedom and incentive to push the boundries of AI video production. Miners will be especially free to explore creatively at the start of the project, when the few guardrails on content will be present. Our goal in this phase is to cast the broadest net to attract top creatives and industry eyes. Eventually miner tasks will be more defined and miners will need to interpret and deliver what the market is asking for. 

InfiniteVibe creative network will fine tune over time to become a full fledged media production studio. AI is rewriting the book (again) on Hollywood and big Media-Tech, and this time Bittensor and InfiniteVibe will become the new leader as THE distributed, decentralized, and ultimately MOST CREATIVE player. 

## Overview

InfiniteVibe implements a decentralized content creation and validation pipeline:
- **Miners** submit video content to the SN and post the content on social media, and eventually the TensorFlix website
- **Validator**  score submissions by their engagement on the video traffic. Validators also: verify content is 100% AI generated, zero illicit or hate speech, traffic is from real humans and not bots. 
- **Coordination** happens through Bittensor blockchain and GitHub gists

## Quick Start

- [Validating](docs/validating.md)
- [Mining](docs/mining.md)
- [How the Subnet Works](docs/how-subnet-works.md)

```mermaid
flowchart TD
    %% ---------- Miners ----------
    subgraph Miners
        M1[Create / Curate<br/>Video or Image Content]
        M2[Publish to YouTube / Instagram<br/>with Required Signature]
        M3[Add / Update Public GitHub Gist<br/>one JSON submission per line]
    end
    M1 --> M2 --> M3
    %% ---------- Bittensor ----------
    BT["TensorFlix Subnet<br/>Subtensor netuid = CONFIG.netuid"]
    M3 --|Gist ID in neuron metadata|--> BT
    %% ---------- Validator ----------
    subgraph Validator
        direction TB
        V0[Start / Timer Tick]
        V1[Metagraph Sync<br/>active miners]
        V2[Fetch Miner Gists<br/>parse → Submissions]
        V3[AI Detector<br/>POST /detect]
        V4[Platform Tracker<br/>GET /get_metrics]
        V5[Verify Signature &<br/>AI-score threshold]
        V6[Compute Engagement EMA<br/>views • likes • comments]
        V7[Aggregate Scores<br/>per Miner]
        V8[Set Weights<br/>on Subtensor]
        DB[(MongoDB Cache)]
    end
    %% ---------- Services ----------
    subgraph Services
        S1[AI Detector Service]
        S2[Platform Tracker Service]
    end
    %% ---------- Data Flow ----------
    V0 --> V1 --> V2
    V2 --> V3 --> S1
    V2 --> V4 --> S2
    V3 --> V5
    V4 --> V5
    V5 --> V6 --> V7 --> V8 --> BT
    %% ---------- Cache taps ----------
    V2 -.-> DB
    V3 -.-> DB
    V4 -.-> DB
    %% ---------- Styling ----------
    classDef cache fill:#fff5d1,stroke:#d4af37,color:#000;
    class DB cache;
```
