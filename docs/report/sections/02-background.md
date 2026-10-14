# 2. Background

## 2.1 Serverless computing

**Serverless computing** is a cloud model in which the provider runs code in response to events
and bills only for the time it executes. There are still servers, but the customer never sees them:
no instance to size, no operating system to patch and nothing running – or billing – when there is
no work. AWS Lambda is the compute part of this model; S3, DynamoDB, SQS, SNS and API Gateway are
its storage, database, messaging and interface counterparts.

## 2.2 Event-driven architecture

In an **event-driven architecture** components do nothing until an event occurs – a file lands in a
bucket, a message arrives in a queue – and then react. ResumeRank's core is one such chain:
*object created* → *message queued* → *function invoked* → *item updated* → *notification
published*. No component polls a folder or runs continuously.

## 2.3 Load balancing and auto scaling without servers

In a server-based design, a **load balancer** spreads requests across several instances and an
**auto scaling group** adds or removes instances as load changes. In a serverless design the same
two properties are provided by the platform: API Gateway accepts and distributes requests at any
volume, and Lambda creates as many concurrent copies of a function as there is work, within limits
the developer sets. A **message queue** between the event source and the function smooths bursts
(queue-based load levelling) and isolates failures (dead-letter queue). §9 shows how ResumeRank
uses each of these and measures the result.

## 2.4 The managed-AI approach

Cloud providers expose trained AI models as pay-per-call APIs: send a document, receive its text;
send text, receive its entities. No model is trained, hosted or tuned by the caller. ResumeRank was
designed around this approach – Textract for OCR and Comprehend for entity extraction – combined
with a transparent, rule-based score so that every result can be explained.

## 2.5 The gap this project addresses

| Requirement | Server-based answer | Serverless answer in ResumeRank |
| --- | --- | --- |
| Cost while idle | instance billed 24 × 7 | Rs. 0 – billed only per use |
| Placement-week burst | resize instances, add a load balancer | API Gateway + SQS + Lambda scale automatically |
| Reading PDFs | install and maintain parsing libraries | managed OCR, with a bundled text-layer fallback |
| Finding skills | regexes or a custom NLP model | 153-skill alias dictionary plus managed NLP |
| Operations | patch, rotate logs, restart on crash | nothing to patch; every invocation logged |
| Upload security | open an upload endpoint on a server | private bucket, pre-signed URLs, no credentials in the browser |
