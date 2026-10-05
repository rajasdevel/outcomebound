# The slicing fixtures' shared ticket store, written into the current directory: the workflow
# document, the ticket template and the store declaration. The setup that sources this sets
# `project` (the tracker's repository name) and `implementers` (the sentence that says who works
# the tickets), and writes its own claims plan, `.outcomebound/ticket-claims.json`.

cat > CONTRIBUTING.md <<EOF
# Contributing

## Tickets

Tickets live on the tracker; \`.outcomebound/tickets.json\` declares it. A ticket is drafted as a
file \`docs/tickets/<name>.md\`: the heading \`# <title>\`, then the body of
\`.github/ISSUE_TEMPLATE/ticket.md\`. In its block, \`reads\` names the design sections the ticket
answers to, as \`<path>#<heading anchor>\`; \`bounds\` the paths its work may write,
comma-separated; \`human-only\` is \`no\` unless a person must do the work; and each \`done-when\`
item names a claim of \`.outcomebound/ticket-claims.json\`. ${implementers}

## How work lands

Each ticket lands as one commit on \`main\`, its message ending with a \`Ticket: #<number>\` line.
EOF

mkdir -p .github/ISSUE_TEMPLATE .outcomebound
cat > .github/ISSUE_TEMPLATE/ticket.md <<'EOF'
## Outcome

## Design

## Tests

## Limits

<!-- outcomebound:begin id=ticket v=1 -->
reads:
bounds:
human-only: no
done-when:
<!-- outcomebound:end id=ticket -->
EOF

cat > .outcomebound/tickets.json <<EOF
{
 "version": 1,
 "store": "github",
 "repo": "example/${project}",
 "label": "ob-ticket",
 "human_label": "human-only",
 "request_label": "human-requested",
 "claims": ".outcomebound/ticket-claims.json",
 "default_branch": "main"
}
EOF
