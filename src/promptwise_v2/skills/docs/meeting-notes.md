---
name: meeting-notes
description: Structure meeting transcripts or notes into decisions, action items, and clean summaries.
triggers:
  - meeting notes
  - meeting summary
  - action items
  - decisions
  - transcript
  - standup
  - retro
depends_on: []
output_schema:
  type: object
  properties:
    decisions:
      type: array
      items:
        type: object
    action_items:
      type: array
      items:
        type: object
    owners:
      type: array
      items:
        type: string
    summary:
      type: string
  required:
    - decisions
    - action_items
    - summary
roles:
  - PM
  - SM
  - EM
model_tier: haiku
---

# Meeting Notes

Structure meeting transcript or notes. Extract: (1) Decisions made (what was agreed, who agreed). (2) Action items: {task, owner, due_date, priority}. (3) Open questions (unresolved, needs follow-up). (4) Key discussion points. For standups: {did_yesterday, doing_today, blockers}. For retros: {went_well, improve, action_items}. Output: structured JSON + clean Markdown summary.

## General Meeting Structure

Extract these elements from any meeting:

### Decisions
```
{
  decision: "what was agreed",
  rationale: "why this was chosen",
  agreed_by: ["name1", "name2"],
  date: "YYYY-MM-DD"
}
```

### Action Items
```
{
  task: "clear, actionable description",
  owner: "person responsible",
  due_date: "YYYY-MM-DD or 'next sprint' or 'EOW'",
  priority: "high | medium | low",
  depends_on: "optional: another task or decision"
}
```

### Open Questions
```
{
  question: "what needs to be answered",
  owner: "person responsible for answering",
  deadline: "when answer is needed"
}
```

## Meeting Type Formats

### Standup
For each participant:
```
{
  name: "participant name",
  did_yesterday: ["completed task 1", "completed task 2"],
  doing_today: ["planned task 1", "planned task 2"],
  blockers: ["blocker description → who can help"]
}
```
Flag blockers that affect the team and require immediate action.

### Sprint Retrospective
```
{
  went_well: ["positive item 1", "positive item 2"],
  improve: ["improvement area 1", "improvement area 2"],
  action_items: [
    {task, owner, sprint_target}
  ],
  team_health: "green | yellow | red"
}
```

### Planning / Design Meeting
- Capture decisions with rationale (decisions that cannot be re-litigated need a clear rationale)
- Flag assumptions made during planning
- Note risks identified and mitigation owners

### 1:1 or Status Meeting
- Focus on action items and unblocking items
- Note any commitments made by either party

## Markdown Summary Format

```markdown
## Meeting: [Title] — [Date]
**Attendees**: name1, name2, name3

### Summary
[2-3 sentence summary of what the meeting covered and outcomes]

### Decisions
- **[Decision]**: [rationale] _(agreed by: name1, name2)_

### Action Items
| # | Task | Owner | Due | Priority |
|---|------|-------|-----|----------|
| 1 | task description | name | date | High |

### Open Questions
- [Question] → owner: name, needed by: date

### Key Discussion Points
- [Point 1]
- [Point 2]
```

## Rules

- Only extract what was explicitly stated — do not infer decisions or commitments
- Action items must have a named owner; if unclear, flag as "owner: TBD"
- Due dates: use explicit dates if stated; otherwise use relative terms (EOW, next sprint, next meeting)
- If a decision was contested or tentative, mark it as `[TENTATIVE]`
- Blockers in standups must be escalated — flag if no owner assigned

## Output

Return structured JSON with decisions, action items (with owner and due date), open questions, and owners list; plus a clean Markdown summary suitable for sharing in Slack or email.
