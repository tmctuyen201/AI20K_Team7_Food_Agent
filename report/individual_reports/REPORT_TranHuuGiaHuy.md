# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Trần Hữu Gia Huy
- **Student ID**: 2A202600426
- **Date**: 2026-04-06

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**: make the mock data and system_prompt for agent (Side quest: Try doing the lab alone: write system prompt(get_system_prompt in agent.py); write ReAct Loop (run in agent.py); write using tool function(_execute_tool in agent.py); write get location function - this one provide a specific location (get_location in food_tools.py); write get time function (get_current_time in food_tools.py); write search food in the user location - this one just provide a specific restaurant base on the input of location (search_food in food_tools.py); 5 main test case for 5 test cases: #1 Happy Case (Luồng chuẩn): Test GPS + Tìm quán, #2 Edge Case 4 (Midnight Craving): Test Tool thời gian, #3 Edge Case 1 (Zero Results): Test việc API không có kết quả, #4 Out of Domain (Từ chối khéo): Test Guardrail không trả lời ngoài lề, #5 Multi-step Reasoning (Tư duy nhiều bước): Kết hợp cả GPS, Giờ, và Món ăn (case 4 use 5 different prompt to try to break the rule))
- **Code Highlights**:
  - \app\main.py
  - \app\agent\prompt.py
  - \app\tools\mock_data.py
  - \app\tools\users.json
  - (Side quest: \huy\src\agent\agent.py, \huy\src\tools\food_tools.py, \huy\main_test_case1.py, \huy\main_test_case2.py, \huy\main_test_case3.py, \huy\main_test_case4.py, \huy\main_test_case5.py)
- **Documentation**: My parsing code acts as a robust middleware between the LLM and the actual tools within the ReAct loop. It scans the LLM's response using Regex to extract the exact `Action` and `Action Input`, which then triggers the corresponding `_execute_tool` function. The most critical technique I implemented here is the `split("Observation:")[0]` safeguard. This logic effectively neutralizes LLM "hallucinations" by stripping away any fabricated text the model attempts to generate after a tool call. It strictly forces the LLM to halt and wait for the *actual* `Observation` from the environment before it can initiate the next Thought-Action cycle.

---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: The ReAct Agent suffered from a "premature execution hallucination." Instead of outputting the `Action Input` and halting to wait for the system to execute the tool, the LLM generated the `Thought`, `Action`, `Action Input`, and immediately hallucinated the `Observation` and `Final Answer` within a single response turn. This behavior bypassed the actual Python tool execution and eventually caused the system to crash with an `AttributeError: 'NoneType' object has no attribute 'group'` during the Regex parsing phase, as the LLM's subsequent response lacked a valid `Action` string.
- **Log Source**: Below is the evidence from the log file demonstrating the Agent hallucinating the execution, which ultimately caused the Parser error:

```json
{"timestamp": "2026-04-06T03:53:47.529320", "event": "AGENT_START", "data": {"input": "T\u00ecm cho t\u00f4i qu\u00e1n \u0111\u1eb7c s\u1ea3n d\u00ea n\u00e0o ngon quanh khu v\u1ef1c t\u00f4i \u0111ang \u0111\u1ee9ng.", "model": "gemini-2.5-flash-lite"}}
{"timestamp": "2026-04-06T03:53:50.687876", "event": "AGENT_END", "data": {"steps": 1, "status": "success", "final_answer": "Qu\u00e1n D\u00ea T\u01b0\u01a1i V\u0129nh L\u1ed9c t\u1ea1i 100 B\u00e0u C\u00e1t, Ph\u01b0\u1eddng 14, Qu\u1eadn T\u00e2n B\u00ecnh, Th\u00e0nh ph\u1ed1 H\u1ed3 Ch\u00ed Minh c\u00f3 c\u00e1c m\u00f3n D\u00ea quay, D\u00ea n\u01b0\u1edbng m\u1ecdi v\u00e0 L\u1ea9u d\u00ea. B\u1ea1n c\u00f3 mu\u1ed1n bi\u1ebft th\u00eam th\u00f4ng tin v\u1ec1 qu\u00e1n n\u00e0y kh\u00f4ng?"}}
```

- **Diagnosis**: The root cause was a combination of the model's natural completion behavior and insufficient constraints in the System Prompt. Because `gemini-2.5-flash-lite` is a fast, lightweight model optimized for standard chat, it naturally attempted to "finish the task" in a single turn. The original prompt lacked explicit negative constraints (e.g., forbidding the word `Observation:`) and strict stopping criteria. As a result, the LLM hallucinated the tool's output to bypass the wait time. Furthermore, the Python parsing logic lacked defensive programming; it assumed the LLM would always perfectly output the `Action:` keyword, which led to the `NoneType` crash when the hallucinated text broke the expected Regex pattern.
- **Solution**: I resolved this issue using a two-pronged approach combining Prompt Engineering and Defensive Programming:
  - **Prompt Enhancement:** I updated the System Prompt with strict negative constraints (e.g., explicitly forbidding the generation of the word `Observation:`) and added clear instructions forcing the LLM to halt after outputting the `Action Input`.
  - **Parser Hardening:** I modified the `run` method in `agent.py` to include a truncation mechanism (`clean_response = response_text.split("Observation:")[0].strip()`). This acts as a hard safeguard: even if the LLM disobeys the prompt and hallucinates the observation, the parser forcefully strips the fake text away, executes the real tool, and appends the authentic `Observation` before continuing the loop. I also added `if action_match:` checks to prevent `NoneType` crashes when the Regex fails.

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1. **Reasoning**:The `Thought` block serves as a cognitive scratchpad that enables the agent to decompose complex queries into sequential, manageable steps. Unlike a standard Chatbot—which relies solely on its internal weights to predict the next token and often hallucinates locations or restaurant data to fulfill the prompt immediately—the ReAct agent uses the `Thought` phase to evaluate its current state and knowledge gaps. For instance, the `Thought` block allows the agent to explicitly deduce, "I do not know the user's current coordinates," which naturally triggers the `get_location` action instead of guessing. This intermediate reasoning step shifts the LLM's behavior from "answering directly" to "planning and executing," thereby grounding the final response in factual, real-time data retrieved by the tools.
2. **Reliability**: The Agent actually performed *worse* than the baseline Chatbot in three specific scenarios. First, regarding  **Latency and Token Efficiency** , the Agent's iterative ReAct loop (Thought -> Action -> Observation) requires multiple API calls, making it significantly slower and more expensive to process than the Chatbot's single-turn generation. Second, for  **General Chit-Chat or Simple Queries** , the Agent's rigid prompt structure and guardrails can make it overly restrictive, sometimes causing it to struggle or unnecessarily refuse basic conversational inputs that a standard Chatbot handles gracefully. Finally, the Agent is  **highly susceptible to formatting failures (Brittleness)** ; if the LLM slightly deviates from the required syntax (e.g., forgetting the `Action:` keyword), the entire Python execution loop crashes, whereas a standard Chatbot is completely immune to parsing errors.
3. **Observation**: The environment feedback (observations) acted as the critical grounding mechanism that dictated the Agent's subsequent decisions. Rather than relying on static or hallucinated data, the Agent used the real-time output from the tools to dynamically shape its next `Thought` and `Action`. For example, receiving the precise GPS address from the `get_location` observation enabled the Agent to accurately append the correct regional context to its `search_food` query. Similarly, receiving a "ZERO_RESULTS" observation from a failed search immediately prevented the Agent from hallucinating a fake restaurant, forcing it to adapt its strategy—such as triggering a fallback response to apologize and ask the user for different preferences—before formulating the `Final Answer`.

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: To scale this ReAct Agent for a production environment with high concurrent traffic, several architectural upgrades are necessary. First, the synchronous execution loop must be refactored to use asynchronous I/O (e.g., `asyncio`) so the server is not blocked while waiting for the LLM or external APIs to respond. Second, implementing an asynchronous message queue (like Celery or RabbitMQ) would help manage and distribute heavy tool-calling workloads across multiple worker nodes. Third, introducing a caching layer (e.g., Redis) to store recent `Observations` (such as user coordinates or frequent restaurant searches) would significantly reduce redundant API calls, mitigate rate-limiting issues, and improve overall system latency. Finally, transitioning from raw Regex parsing to native, structured LLM Function Calling (via JSON schemas) would drastically improve parsing reliability at scale.
- **Safety**:To enhance the system's safety and robustness against malicious inputs or erratic LLM behavior, several defensive layers should be implemented. Relying solely on prompt-based guardrails is insufficient for a production environment. A dedicated 'Supervisor' LLM could be introduced to independently audit the ReAct agent's generated `Action` and `Action Input` before the Python environment actually executes the tool, ensuring the agent does not attempt unauthorized or off-topic operations. Additionally, implementing an external, deterministic framework (such as semantic routing or NeMo Guardrails) would provide robust input/output sanitization to prevent prompt injection attacks. Finally, for any tools that modify user data or incur costs, strict Role-Based Access Control (RBAC) and a hard-coded execution timeout should be enforced to prevent the agent from autonomously causing harm.
- **Performance**: To optimize the Agent's performance, particularly as the system expands to include dozens or hundreds of tools, hardcoding every tool description into the system prompt becomes highly inefficient and increases latency. A robust solution is to implement a Vector Database for dynamic tool retrieval. By performing a semantic search based on the user's query, the system can dynamically retrieve and inject only the top-K most relevant tools into the context window. This approach significantly reduces token consumption, minimizes the risk of the LLM getting confused by an overloaded prompt, and drastically improves inference speed. Furthermore, leveraging prompt caching for static instructions and fine-tuning smaller, specialized models purely for function-calling can further minimize the latency of each Thought-Action cycle.

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.
