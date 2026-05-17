# Eason Report Quality Rubric (judge)

Score each 0-2 (0 absent/wrong, 1 partial, 2 good). Output strict JSON:
`{"sections":N,"calendar":N,"freshness":N,"picks":N,"overall":N,"notes":"..."}`

- sections: required sections present (5-layer signals, overall signal, key levels, narrative, picks).
- calendar: every date/weekday/holiday statement matches the injected calendar facts.
- freshness: no news item older than 7 days or future-dated treated as current.
- picks: each pick has ticker + entry + signal, well-formed.
- overall: holistic — would this pass as a genuine Eason-style brief.
