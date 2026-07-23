### Client Communication Strategy

We chose REST communication between the Client Web Interface and the AI Query Service.

Each user question is independent and does not require a persistent connection.

REST provides:
- simpler implementation
- easier debugging
- clear request/response communication
- sufficient performance for this use case

WebSockets were considered but rejected because real-time streaming is not required.

## Example Questions

### Product information

"What is the description of product 123?"

### Stock availability

"Which branch has product 123?"

### Branch products

"What products are available in Paris branch?"

### Shopping recommendation

"I need 3 laptops and 2 keyboards. 
Which branch should I visit?"
