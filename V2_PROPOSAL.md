# V2 proposal

**Status:** V2 implemented: async trace append.

Observed evidence: V1 `complete()` waited on a synchronous `INSERT` into `aicp_traces`. Against a 5 ms fake provider that overhead was visible (p50 ~0.86 ms). Against a real model it would not dominate, but the loss policy was still undefined.

Chosen solution: bounded in-memory queue + background writer. The caller still gets the model result if the queue is full (`aicp_trace_queue_drop_total`) or the write fails (`aicp_trace_write_fail_total`). Budget and kill switch stay synchronous. `TRACE_ASYNC=false` restores V1 (tests use this).

Rejected: Kafka, dual-write to a second store, dropping traces silently without a metric.
