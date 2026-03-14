/**
 * Promptfoo assertion helpers for instruction compliance testing.
 *
 * Usage in promptfoo YAML:
 *   type: javascript
 *   value: |
 *     const { toolWasCalled } = require('./evals/lib/assert-tool-called');
 *     return toolWasCalled('Grep')(output, context);
 *
 * Or inline (avoids require() path resolution):
 *   type: javascript
 *   value: |
 *     const toolCalls = context.providerResponse?.metadata?.toolCalls ?? [];
 *     return toolCalls.some(c => c.name === 'Grep');
 */

/**
 * Returns a promptfoo assertion function that passes when a tool was called.
 *
 * @param {string} toolName - Tool name (e.g. 'Bash', 'Grep', 'mcp__shodh-memory__context_summary')
 * @param {string} [inputPattern] - Optional regex string matched against JSON.stringify(call.input)
 */
function toolWasCalled(toolName, inputPattern) {
  const regex = inputPattern ? new RegExp(inputPattern) : null;
  return (_output, context) => {
    const toolCalls = context.providerResponse?.metadata?.toolCalls ?? [];
    const match = toolCalls.find((c) => {
      if (c.name !== toolName) return false;
      if (!regex) return true;
      return regex.test(JSON.stringify(c.input ?? {}));
    });
    return {
      pass: !!match,
      score: match ? 1 : 0,
      reason: match
        ? `✓ ${toolName}${inputPattern ? ` matching /${inputPattern}/` : ''} was called`
        : `✗ ${toolName}${inputPattern ? ` matching /${inputPattern}/` : ''} not found. Calls: [${toolCalls.map((c) => c.name).join(', ') || 'none'}]`,
    };
  };
}

/**
 * Returns a promptfoo assertion function that passes when a tool was NOT called.
 *
 * @param {string} toolName - Tool name to assert was not used
 * @param {string} [inputPattern] - Optional regex string matched against JSON.stringify(call.input)
 */
function toolWasNotCalled(toolName, inputPattern) {
  const regex = inputPattern ? new RegExp(inputPattern) : null;
  return (_output, context) => {
    const toolCalls = context.providerResponse?.metadata?.toolCalls ?? [];
    const violations = toolCalls.filter((c) => {
      if (c.name !== toolName) return false;
      if (!regex) return true;
      return regex.test(JSON.stringify(c.input ?? {}));
    });
    return {
      pass: violations.length === 0,
      score: violations.length === 0 ? 1 : 0,
      reason:
        violations.length === 0
          ? `✓ ${toolName}${inputPattern ? ` matching /${inputPattern}/` : ''} correctly not called`
          : `✗ ${toolName}${inputPattern ? ` matching /${inputPattern}/` : ''} called ${violations.length} time(s): ${JSON.stringify(violations.map((c) => c.input))}`,
    };
  };
}

module.exports = { toolWasCalled, toolWasNotCalled };
