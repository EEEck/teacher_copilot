param(
    [string]$ApiBase = "http://localhost:8010",
    [string]$ClassId = "chemie_9b_2026_27",
    [string]$OutputRoot = "backend/runs",
    [string]$RunName = ""
)

$ErrorActionPreference = "Stop"

if (-not $RunName) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $RunName = "$stamp-fckw-plan-2turn"
}

$runDir = Join-Path $OutputRoot $RunName
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$base = "$ApiBase/api/classes/$ClassId/plan/sessions"
$session = Invoke-RestMethod -Method Post -Uri $base -ContentType "application/json" -Body "{}"

$prompt1 = @'
Plan the next 45-minute lesson for Chemie 9b. Topic: redox reactions applied to CFC/FCKW compounds (Chlorfluorkohlenwasserstoffe). Include about 10 minutes on environmental impact (ozone layer, Montreal Protocol, alternatives). Build on our existing redox lessons in the wiki. Exam-oriented Gymnasium level.
Structure the lesson flow: 5 min redox recap, 15 min FCKW structure and redox half-reactions, 10 min environmental impact with one example (e.g. CFC-11), 10 min practice, 5 min exit ticket. Note the misconception: oxidation number vs charge.
Add differentiated practice and homework (2 questions). Teacher notes: no real CFCs in the lab; demo alternatives only.
'@

$prompt2 = @'
Can we also add a 5 min review session of the last 4 lectures? I would like to consider what the class confused the last few sessions and incorporate key findings to make the introduction of FCKW simpler for them to digest.
'@

function Write-JsonFile($Value, [string]$Path, [int]$Depth = 80) {
    $Value | ConvertTo-Json -Depth $Depth | Set-Content -Path $Path -Encoding UTF8
}

function Write-TextFile([string]$Value, [string]$Path) {
    $Value | Set-Content -Path $Path -Encoding UTF8
}

function Write-TraceFiles($Trace, [string]$Path) {
    Write-JsonFile $Trace $Path 100
}

function Write-PromptAssemblyFiles($Assembly, [string]$Prefix, [string]$Title) {
    Write-JsonFile $Assembly "$Prefix.json" 80
    Write-TextFile $Assembly.instructions "$Prefix-instructions.txt"
    Write-TextFile $Assembly.user_input "$Prefix-user-input.txt"

    $lines = @()
    $lines += "# $Title"
    $lines += ""
    $lines += "Stage: $($Assembly.stage)"
    $lines += "Model call: $($Assembly.model_call)"
    $lines += "Instruction chars: $($Assembly.instruction_chars)"
    $lines += "User input chars: $($Assembly.user_input_chars)"
    $lines += ""
    $lines += "## Sections"
    foreach ($sec in $Assembly.sections) {
        $lines += ""
        $lines += "### $($sec.name)"
        $lines += "- function: ``$($sec.function)``"
        $lines += "- source: ``$($sec.source)``"
        $lines += "- included: $($sec.included)"
        $lines += "- chars: $($sec.chars)"
        $lines += ""
        $lines += '```text'
        $lines += [string]$sec.text
        $lines += '```'
    }
    if ($Assembly.nested.class_slice.sections) {
        $lines += ""
        $lines += "## Nested Class Slice"
        foreach ($sec in $Assembly.nested.class_slice.sections) {
            $lines += ""
            $lines += "### $($sec.name)"
            $lines += "- function: ``$($sec.function)``"
            $lines += "- source: ``$($sec.source)``"
            $lines += "- included: $($sec.included)"
            $lines += "- chars: $($sec.chars)"
            $lines += ""
            $lines += '```text'
            $lines += [string]$sec.text
            $lines += '```'
        }
    }
    Write-TextFile ($lines -join "`n") "$Prefix-sections.md"
}

$meta = [ordered]@{
    run_dir = $runDir
    created_at = (Get-Date).ToString("o")
    api_base = $ApiBase
    class_id = $ClassId
    session_id = $session.session_id
    prompts = @($prompt1, $prompt2)
}
Write-JsonFile $meta (Join-Path $runDir "00-run-meta.json") 10
Write-JsonFile $session (Join-Path $runDir "01-session-start.json") 10

$trace0 = Invoke-RestMethod -Method Get -Uri "$base/$($session.session_id)/trace"
Write-TraceFiles $trace0 (Join-Path $runDir "02-trace-before-first-message.json")
Write-PromptAssemblyFiles $trace0.prompt_assembly (Join-Path $runDir "snapshot-00-before-first-message") "Snapshot 00 - Before First Message"

$turn1Body = @{ message = $prompt1 } | ConvertTo-Json
$turn1 = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/$($session.session_id)/chat/stream" -ContentType "application/json" -Body $turn1Body -TimeoutSec 240
Write-TextFile $turn1.Content (Join-Path $runDir "03-turn1-sse.txt")

$trace1 = Invoke-RestMethod -Method Get -Uri "$base/$($session.session_id)/trace"
Write-TraceFiles $trace1 (Join-Path $runDir "04-trace-after-turn1.json")
Write-PromptAssemblyFiles $trace1.prompt_assembly (Join-Path $runDir "snapshot-01-after-turn1-next-prompt") "Snapshot 01 - After Turn 1 Next Prompt"

$turn2Body = @{ message = $prompt2 } | ConvertTo-Json
$turn2 = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$base/$($session.session_id)/chat/stream" -ContentType "application/json" -Body $turn2Body -TimeoutSec 240
Write-TextFile $turn2.Content (Join-Path $runDir "05-turn2-sse.txt")

$trace2 = Invoke-RestMethod -Method Get -Uri "$base/$($session.session_id)/trace"
Write-TraceFiles $trace2 (Join-Path $runDir "06-trace-after-turn2.json")
Write-PromptAssemblyFiles $trace2.prompt_assembly (Join-Path $runDir "snapshot-02-after-turn2-next-prompt") "Snapshot 02 - After Turn 2 Next Prompt"
Write-TextFile $trace2.artifact_markdown (Join-Path $runDir "07-final-lessonplan.md")

$assemblies = @($trace2.event_trace | Where-Object { $_.type -eq "prompt_assembly" })
for ($i = 0; $i -lt $assemblies.Count; $i++) {
    $n = "{0:D2}" -f ($i + 1)
    $a = $assemblies[$i]
    $prefix = Join-Path $runDir ("prompt-$n-" + $a.stage)
    Write-PromptAssemblyFiles $a $prefix "Prompt $n - $($a.stage)"
}

$toolLines = @("# Tool Calls And Results", "")
$toolIndex = 0
foreach ($e in $trace2.event_trace) {
    if ($e.type -eq "tool_call") {
        $toolIndex++
        $toolLines += "## Tool call $toolIndex - $($e.name)"
        $toolLines += ""
        $toolLines += "Call id: ``$($e.call_id)``"
        $toolLines += ""
        $toolLines += '```json'
        $toolLines += [string]$e.args
        $toolLines += '```'
        $toolLines += ""
    } elseif ($e.type -eq "tool_result") {
        $toolLines += "### Result"
        $toolLines += ""
        $toolLines += "Call id: ``$($e.call_id)``"
        $toolLines += ""
        $toolLines += '```text'
        $toolLines += [string]$e.output
        $toolLines += '```'
        $toolLines += ""
    }
}
Write-TextFile ($toolLines -join "`n") (Join-Path $runDir "08-tool-calls-and-results.md")

$rawDir = Join-Path $runDir "raw-evidence"
New-Item -ItemType Directory -Force -Path $rawDir | Out-Null
foreach ($p in $trace2.raw_evidence.PSObject.Properties) {
    Write-TextFile ([string]$p.Value) (Join-Path $rawDir "$($p.Name).txt")
}

$report = @()
$report += "# FCKW Plan Run Report"
$report += ""
$report += "Run directory: ``$runDir``"
$report += "Session id: ``$($session.session_id)``"
$report += "Class: ``$ClassId``"
$report += "Created: $((Get-Date).ToString('o'))"
$report += ""
$report += "## Files"
$report += "- ``00-run-meta.json``: prompt inputs and run metadata"
$report += "- ``01-session-start.json``: API session start response"
$report += "- ``02-trace-before-first-message.json``: exact trace before any chat"
$report += "- ``03-turn1-sse.txt``: raw SSE stream for turn 1"
$report += "- ``04-trace-after-turn1.json``: trace after first teacher prompt"
$report += "- ``05-turn2-sse.txt``: raw SSE stream for turn 2"
$report += "- ``06-trace-after-turn2.json``: final full trace"
$report += "- ``07-final-lessonplan.md``: final teacher-facing plan artifact"
$report += "- ``prompt-XX-*-instructions.txt``: exact model instructions for each model call"
$report += "- ``prompt-XX-*-user-input.txt``: exact user input for each model call"
$report += "- ``prompt-XX-*-sections.md``: readable section-by-section context"
$report += "- ``snapshot-00-before-first-message-*``: exact prompt stack before any chat"
$report += "- ``snapshot-01-after-turn1-next-prompt-*``: exact prompt stack after turn 1 if another turn starts"
$report += "- ``snapshot-02-after-turn2-next-prompt-*``: exact prompt stack after turn 2 if another turn starts"
$report += "- ``08-tool-calls-and-results.md``: tool call inputs and streamed outputs"
$report += "- ``raw-evidence/``: full captured tool outputs by raw_ref"
$report += ""
$report += "## Prompt Calls"
for ($i = 0; $i -lt $assemblies.Count; $i++) {
    $n = "{0:D2}" -f ($i + 1)
    $a = $assemblies[$i]
    $report += "### $n - $($a.stage)"
    $report += "- Model call: ``$($a.model_call)``"
    $report += "- Instructions: $($a.instruction_chars) chars"
    $report += "- User input: $($a.user_input_chars) chars"
    $report += "- Exact instructions: ``prompt-$n-$($a.stage)-instructions.txt``"
    $report += "- Exact user input: ``prompt-$n-$($a.stage)-user-input.txt``"
    $report += "- Section view: ``prompt-$n-$($a.stage)-sections.md``"
    $report += ""
}
$report += "## Tool Calls"
foreach ($e in $trace2.event_trace | Where-Object { $_.type -eq "tool_call" }) {
    $report += "- ``$($e.name)`` with args: ``$($e.args)``"
}
$report += ""
$report += "## Raw Evidence Refs"
foreach ($p in $trace2.raw_evidence.PSObject.Properties) {
    $report += "- ``$($p.Name)`` -> ``raw-evidence/$($p.Name).txt`` ($($p.Value.Length) chars)"
}
$report += ""
$report += "## What The LLM Knew At Each Step"
$report += "- Before first message: no conversation yet; trace shows default plan-chat stack and empty artifact template."
$report += "- Lazy opening call: compact class slice only plus opening instructions."
$report += "- First planning call: compact class slice, teacher/copilot profiles, empty runtime state, empty plan artifact, no evidence briefs, opening assistant message, and teacher FCKW prompt."
$report += "- Second planning call: same compact class slice plus updated runtime state, current full lesson artifact, compact evidence briefs, full recent conversation window, and raw evidence refs available via tool."
$report += ""
$report += "## Quick Quality Notes"
$report += "- Use ``prompt-*-sections.md`` to inspect exact context, not ``context-current.txt``."
$report += "- Use ``08-tool-calls-and-results.md`` and ``raw-evidence/`` to inspect what tools actually returned."
$report += "- ``context-current.txt`` is legacy stacked context and should be retired or regenerated from this run-bundle format."
Write-TextFile ($report -join "`n") (Join-Path $runDir "README.md")

Write-Output "run_dir=$runDir"
Write-Output "session_id=$($session.session_id)"
Write-Output "prompt_calls=$($assemblies.Count)"
Write-Output "tool_calls=$(($trace2.event_trace | Where-Object { $_.type -eq 'tool_call' }).Count)"
Write-Output "raw_evidence=$(@($trace2.raw_evidence.PSObject.Properties).Count)"
