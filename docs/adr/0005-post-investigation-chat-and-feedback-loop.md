# Post-Investigation Chat and Continuous Feedback Loop

We decided to support stateful interactive conversations on completed investigations via LangGraph checkpoint persistence. An Entry Router inspects the thread state to route follow-ups into a tool-enabled Chat Agent capable of live verification, specialist re-runs, and custom analyses without losing prior incident context. A structured 1-5 star review system with free-text feedback is attached to capture continuous signal on prompt efficacy and false-positive rates.
