# System Design course: lesson topics

The course has four parts:
- **Part 2** follows the chapters and sections of *Designing Data-Intensive Applications*, 2nd edition (Martin
  Kleppmann and Chris Riccomini, O'Reilly, 2026). Only the book's headings were used, to set the order and the
  scope. Each lesson is researched and written by the pipeline itself, never taken from the book.
- **Parts 1, 3 and 4** cover what a complete system design course needs and the book leaves out: the building
  blocks, resilience and operations, and the classic design case studies.

How to run one: Actions > Make a video, then paste ONE line as the topic. Use style `education` and level
`intermediate`. Run it in its own workflow run, next to the day's Statistics run.

## Part 1. Foundations: the building blocks
1. System Design: what system design is and how to approach a design problem
2. System Design: back-of-the-envelope estimation, latency numbers, QPS and storage math
3. System Design: how a request travels the internet, DNS, TCP, UDP and HTTP
4. System Design: HTTP/1.1 vs HTTP/2 vs HTTP/3, HTTPS and TLS
5. System Design: load balancers, layer 4 vs layer 7, algorithms and health checks
6. System Design: reverse proxies, API gateways and service discovery
7. System Design: caching strategies, cache-aside, write-through, write-back and LRU eviction
8. System Design: CDNs and edge caching
9. System Design: cache invalidation, cache stampedes and hot keys
10. System Design: API styles compared, REST vs GraphQL vs gRPC
11. System Design: API design details, pagination, versioning and idempotency keys
12. System Design: rate limiting, token bucket, leaky bucket and sliding window
13. System Design: blob and object storage (S3-style)
14. System Design: real-time updates, polling, long polling, WebSockets and server-sent events

## Part 2. Data-intensive systems (the book's chapters)
### Trade-offs in data systems architecture
15. System Design: OLTP vs OLAP, operational vs analytical systems
16. System Design: data warehouses, data lakes, systems of record and derived data
17. System Design: cloud vs self-hosting and cloud-native architecture
18. System Design: distributed vs single-node systems, microservices and serverless
### Defining nonfunctional requirements
19. System Design: case study, social network home timelines (fan-out on write vs on read)
20. System Design: describing performance, latency, response time and percentiles (p50, p99)
21. System Design: reliability and fault tolerance, hardware, software and human faults
22. System Design: scalability, describing load and shared-nothing architecture
23. System Design: maintainability, operability, simplicity and evolvability
### Data models and query languages
24. System Design: relational vs document databases and the object-relational mismatch
25. System Design: normalization, denormalization, many-to-one and many-to-many relationships
26. System Design: star and snowflake schemas for analytics
27. System Design: graph data models, property graphs, Cypher, triple stores and SPARQL
28. System Design: recursive queries, Datalog and graph queries in SQL
29. System Design: event sourcing and CQRS
30. System Design: DataFrames, matrices and arrays as data models
### Storage and retrieval
31. System Design: log-structured storage, SSTables and LSM-trees
32. System Design: B-trees and how database indexes work
33. System Design: B-trees vs LSM-trees, which one and why
34. System Design: multicolumn, secondary and covering indexes, and in-memory databases
35. System Design: cloud data warehouses and column-oriented storage
36. System Design: vectorized query execution, materialized views and data cubes
37. System Design: full-text search and inverted indexes
38. System Design: vector embeddings and vector search indexes
### Encoding and evolution
39. System Design: encoding data, JSON vs Protocol Buffers vs Avro
40. System Design: schemas and schema evolution, backward and forward compatibility
41. System Design: dataflow through databases and services, REST and RPC
42. System Design: durable execution and workflow engines
43. System Design: event-driven architectures
### Replication
44. System Design: single-leader replication, sync vs async followers and failover
45. System Design: how replication logs work, statement-based, WAL and logical replication
46. System Design: replication lag, read-your-writes and monotonic reads
47. System Design: multi-leader replication and multi-region databases
48. System Design: sync engines and local-first software
49. System Design: conflicting writes, last-write-wins, CRDTs and operational transformation
50. System Design: leaderless replication, quorums and read repair
51. System Design: detecting concurrent writes with version vectors
### Sharding
52. System Design: why shard, and sharding for multitenancy
53. System Design: sharding by key range vs hash, and consistent hashing
54. System Design: hot spots, skewed workloads and rebalancing shards
55. System Design: request routing in sharded databases
56. System Design: local vs global secondary indexes
### Transactions
57. System Design: what a transaction is, ACID explained
58. System Design: read committed, snapshot isolation and MVCC
59. System Design: lost updates, write skew and phantoms
60. System Design: serial execution and two-phase locking
61. System Design: serializable snapshot isolation
62. System Design: distributed transactions and two-phase commit
63. System Design: exactly-once message processing
### The trouble with distributed systems
64. System Design: partial failures, unreliable networks and the limits of TCP
65. System Design: fault detection, timeouts and unbounded delays
66. System Design: unreliable clocks, monotonic vs time-of-day clocks and clock sync
67. System Design: process pauses, distributed locks, leases and fencing tokens
68. System Design: Byzantine faults and system models
69. System Design: formal methods and randomized testing (TLA+, Jepsen, chaos testing)
### Consistency and consensus
70. System Design: linearizability, the strongest consistency
71. System Design: the CAP theorem and the cost of linearizability
72. System Design: ID generators and logical clocks, Lamport timestamps and Snowflake IDs
73. System Design: consensus with Raft and Paxos, and leader election
74. System Design: coordination services, ZooKeeper and etcd
### Batch processing
75. System Design: batch processing with Unix tools
76. System Design: distributed filesystems, object stores and job orchestration
77. System Design: MapReduce and dataflow engines (Spark), shuffles, joins and grouping
78. System Design: batch use cases, ETL, analytics, machine learning and serving derived data
### Stream processing
79. System Design: messaging systems and log-based brokers, Kafka explained
80. System Design: change data capture
81. System Design: state, streams and immutability
82. System Design: reasoning about time in streams, windows and watermarks
83. System Design: stream joins and fault tolerance in stream processing
### A philosophy of streaming systems
84. System Design: data integration, combining batch and stream processing (Lambda vs Kappa)
85. System Design: unbundling the database and designing applications around dataflow
86. System Design: correctness, the end-to-end argument, constraints, timeliness vs integrity
### Doing the right thing
87. System Design: predictive analytics, bias, accountability and feedback loops
88. System Design: privacy, tracking, consent and data protection laws

## Part 3. Resilience and operations
89. System Design: circuit breakers, retries with exponential backoff and bulkheads
90. System Design: the saga pattern for transactions across microservices
91. System Design: observability, logs, metrics and distributed tracing
92. System Design: deployments, blue-green, canary releases and feature flags
93. System Design: containers and Kubernetes for system design
94. System Design: authentication and authorization, sessions, OAuth 2.0 and JWT
95. System Design: geospatial indexing, geohash and quadtrees

## Part 4. Case studies: designing real systems
96. System Design: design a URL shortener
97. System Design: design a distributed key-value store
98. System Design: design a chat application like WhatsApp
99. System Design: design a notification system
100. System Design: design a web crawler
101. System Design: design search autocomplete (typeahead)
102. System Design: design a video streaming platform like YouTube
103. System Design: design a file sync service like Dropbox
104. System Design: design a ride-sharing service like Uber
105. System Design: design a proximity service (nearby places)
106. System Design: design a distributed message queue
107. System Design: design a metrics monitoring and alerting system
108. System Design: design a payment system
109. System Design: design a hotel reservation system
110. System Design: design a real-time gaming leaderboard
111. System Design: design a stock exchange
