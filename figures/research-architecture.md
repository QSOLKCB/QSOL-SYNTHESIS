# Research architecture (working synthesis)

~~~mermaid
flowchart TD
  A[SOURCE / STATE] --> B[TRANSFORMATION]
  B --> C[OBSERVATION]
  C --> D[COMPARISON / VALIDATION]
  D --> E{SUPPORTED UNDER DECLARED CONTRACT?}
  E -- no --> F[REJECT / QUALIFY / RETAIN ORACLE]
  E -- yes --> G[RECOVERY / PRESERVATION / PROMOTION]
  G --> H[PROVENANCE + REPLAY]
  H --> I[INTERPRETATION WITH CLAIM BOUNDARIES]
~~~

Not every project implements every stage. The diagram is a comparison tool, not a universal physical model.
