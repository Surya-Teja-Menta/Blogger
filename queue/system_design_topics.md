# System Design course: lesson topics

The order follows the chapters of *Designing Data-Intensive Applications*, 2nd edition (Martin Kleppmann and Chris
Riccomini, O'Reilly, 2026). Only the chapter list was used, to set the order and the scope. Each lesson is
researched and written by the pipeline itself, never taken from the book.

How to run one: Actions > Make a video, then paste ONE line as the topic. Use style `education` and level
`intermediate`. Run it in its own workflow run, next to the day's Statistics run.

## 1. Trade-offs in data systems architecture
1. System Design: OLTP vs OLAP, operational vs analytical systems
2. System Design: data warehouses, data lakes, systems of record and derived data
3. System Design: cloud vs self-hosting, and distributed vs single-node systems

## 2. Defining nonfunctional requirements
4. System Design: describing load and performance, throughput, response time and percentiles (p50, p99)
5. System Design: reliability and fault tolerance, faults vs failures
6. System Design: scalability, vertical vs horizontal scaling and shared-nothing architecture
7. System Design: maintainability, operability, simplicity and evolvability

## 3. Data models and query languages
8. System Design: relational vs document databases (SQL vs NoSQL)
9. System Design: normalization, denormalization and joins
10. System Design: graph data models and graph queries
11. System Design: event sourcing and CQRS

## 4. Storage and retrieval
12. System Design: log-structured storage, SSTables and LSM-trees
13. System Design: B-trees and how database indexes work
14. System Design: Bloom filters, secondary indexes and in-memory databases
15. System Design: column-oriented storage for analytics
16. System Design: full-text search and vector search indexes

## 5. Encoding and evolution
17. System Design: encoding data, JSON vs Protocol Buffers vs Avro
18. System Design: schema evolution, backward and forward compatibility
19. System Design: dataflow between services, REST, RPC and message brokers
20. System Design: durable execution and workflow engines

## 6. Replication
21. System Design: single-leader replication, leaders and followers
22. System Design: replication lag, read-your-writes and monotonic reads
23. System Design: multi-leader replication and conflict resolution (CRDTs)
24. System Design: leaderless replication and quorums

## 7. Sharding
25. System Design: sharding by key range vs hash, and consistent hashing
26. System Design: hot spots, skewed workloads and rebalancing shards
27. System Design: request routing and secondary indexes in sharded databases

## 8. Transactions
28. System Design: ACID transactions explained
29. System Design: isolation levels, read committed and snapshot isolation
30. System Design: lost updates, write skew and phantoms
31. System Design: serializability, two-phase locking and serializable snapshot isolation
32. System Design: distributed transactions and two-phase commit

## 9. The trouble with distributed systems
33. System Design: partial failures and unreliable networks
34. System Design: unreliable clocks, clock skew and ordering events
35. System Design: process pauses, leases and fencing tokens

## 10. Consistency and consensus
36. System Design: linearizability, the strongest consistency
37. System Design: the CAP theorem explained honestly
38. System Design: logical clocks, Lamport timestamps and ordering
39. System Design: consensus with Raft and Paxos, and leader election
40. System Design: coordination services, ZooKeeper and etcd

## 11. Batch processing
41. System Design: batch processing from Unix pipes to MapReduce
42. System Design: distributed joins, Spark and dataflow engines

## 12. Stream processing
43. System Design: message brokers and logs, Kafka explained
44. System Design: change data capture and event streams
45. System Design: stream processing windows, joins and exactly-once

## 13. A philosophy of streaming systems
46. System Design: unbundling the database, derived data and dataflow
47. System Design: end-to-end correctness and idempotence

## 14. Doing the right thing
48. System Design: ethics of data systems, privacy, surveillance and bias
