// Model id and nickname to rung (the `tier` of agents_inc/models.json). tests/test_delegate_pane_rungs.py parses the
// entries between the markers below and fails when one is missing, drifts from models.json or from MODEL_RUNG in
// skills/workerbee/scripts/dispatch_rungs.py, or is written in a form it does not parse. Unknown names are not listed: the pane
// shows `?` for them (rungOf in mission.ts).
// RUNGS-BEGIN
export const RUNGS: Record<string, string> = {
  // models.json ids
  'haiku': 'grunt',
  'sonnet': 'workhorse',
  'opus': 'orchestrator',
  'fable': 'executive',
  'gpt-5.4-mini': 'grunt',
  'gpt-5.6-luna': 'grunt',
  'gpt-5.6-terra': 'workhorse',
  'gpt-5.6-sol': 'orchestrator',
  'gpt-6-astra': 'executive',
  'gemini-2.5-flash': 'grunt',
  'gemini-flash-lite': 'grunt',
  'gemini-flash-lite-latest': 'grunt',
  'gemini-3.8-flash': 'grunt',
  'codestral-latest': 'grunt',
  'ministral-3b-latest': 'grunt',
  'openrouter/auto:free': 'grunt',
  'dots-studio/dots-3-note-preview:free': 'grunt',
  'liquid/lfm-2.5-2.6b:free': 'grunt',
  'nvidia/nemotron-3.5-lightning:free': 'grunt',
  'cohere/north-mini-code:free': 'grunt',
  'nvidia/nemotron-3-ultra-550b-a55b:free': 'grunt',
  'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free': 'grunt',
  'google/gemma-4-26b-a4b-it:free': 'grunt',
  'google/gemma-4-31b-it:free': 'grunt',
  'google/lyria-3-pro-preview': 'grunt',
  'google/lyria-3-clip-preview': 'grunt',
  'openrouter/free': 'grunt',
  'qwen2.5-coder:3b': 'grunt',
  'qwen2.5-coder:7b': 'grunt',
  'qwen3:8b': 'grunt',
  'gpt-6-luna': 'grunt',
  'gpt-6.1-sol': 'orchestrator',
  'gpt-6.1-terra': 'workhorse',
  // models.json nicknames
  'gemini-flash': 'grunt',
  'codestral': 'grunt',
  'ministral': 'grunt',
  'dots-note': 'grunt',
  'nemotron-lightning': 'grunt',
  'nemotron-ultra': 'grunt',
  'nemotron-nano': 'grunt',
  'gemma-26b': 'grunt',
  'gemma-31b': 'grunt',
  // MODEL_RUNG aliases (skills/workerbee/scripts/dispatch_rungs.py) that are no id or nickname
  'luna': 'grunt',
  'terra': 'workhorse',
  'sol': 'orchestrator',
  'astra': 'executive',
}
// RUNGS-END
