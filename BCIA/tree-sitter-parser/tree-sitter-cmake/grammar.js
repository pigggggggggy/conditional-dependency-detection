keywords = [
  "if",
  "elseif",
  "else",
  "endif",
  "foreach",
  "endforeach",
  "while",
  "endwhile",
  "function",
  "endfunction",
  "macro",
  "endmacro",
  "block",
  "endblock",
];

module.exports = grammar({
  name: "cmake",

  externals: ($) => [$.bracket_argument, $.bracket_comment, $.line_comment],
  extras: (_) => [/\s/],

  rules: {
    source_file: ($) => repeat($._statement),

    escape_sequence: ($) => choice($._escape_identity, $._escape_encoded, $._escape_semicolon),
    _escape_identity: (_) => /\\[^A-Za-z0-9;]/,
    _escape_encoded: (_) => choice("\\t", "\\r", "\\n"),
    _escape_semicolon: (_) => choice(";", "\\;"),

    variable: ($) => prec.left(repeat1(choice($.variable_text, $.escape_sequence, $.variable_ref))),
    variable_text: (_) => /[a-zA-Z0-9/_.+-]+/,
    variable_ref: ($) => choice($.normal_var, $.env_var, $.cache_var),
    normal_var: ($) => seq(alias(/\$\s*\{/, "var_s"), $.variable, alias(/\}/, "var_e")),
    env_var: ($) => seq(alias(/\$\s*[E|e][N|n][V|v]\s*\{/, "var_s"), $.variable, alias(/\}/, "var_e")),
    cache_var: ($) => seq(alias(/\$\s*[C|c][A|a][C|c][H|h][E|e]\s*\{/, "var_s"), $.variable, alias(/\}/, "var_e")),

    gen_exp: ($) => seq(alias(/\$\s*</, "gen_exp_s"), optional($._gen_exp_content), alias(/>/, "gen_exp_e")),
    _gen_exp_content: ($) => repeat1(choice($.gen_exp, $.variable_ref, $.gen_exp_text, alias(/[:,;]/, "sep"))),
    // gen_exp_text: ($) => /[a-zA-Z0-9/_.=+\^\\\(\)"\[\]-]+/, // TODO (CAVEAT): This might not be complete
    gen_exp_text: (_) => /[^:,;">]+/, // TODO (CAVEAT): Fails if someone uses > inside the text.

    _argument: ($) => choice($.bracket_argument, $.quoted_argument, $.unquoted_argument),
    _untrimmed_argument: ($) => choice(/\s/, $.bracket_comment, $.line_comment, $._argument, $._paren_argument),
    _paren_argument: ($) => seq("(", repeat($._untrimmed_argument), ")"),

    quoted_argument: ($) => seq('"', optional($._quoted_element), '"'),
    _quoted_element: ($) =>
      choice(
        prec.right(repeat1(choice($.quoted_text, $.variable_ref, $.gen_exp, $.escape_sequence))),
        alias(/\$\s*</, "quoted_text")
      ),
    quoted_text: (_) => choice(/\$/, /[^\\"\$]+/), // NOTE: The $ char is stored in a separate node

    unquoted_argument: ($) =>
      prec.right(repeat1(choice($.unquoted_text, $.variable_ref, $.gen_exp, $.escape_sequence))),
    unquoted_text: (_) => choice(/\$/, /[^\s()#"\\\$]+/), // NOTE: The $ char is stored in a separate node

    condition: ($) => seq("(", repeat($._untrimmed_argument), ")"), /// TODO: Improve to take operators
    body: ($) => repeat1($._statement), /// NOTE: To allow for empty body, use optional($.body)

    if_clause: ($) => seq($.if, $.condition, optional($.body)),
    elseif_clause: ($) => seq($.elseif, $.condition, optional($.body)),
    else_clause: ($) => seq($.else, $.condition, optional($.body)),
    endif_clause: ($) => seq($.endif, $.condition),
    if_statement: ($) => seq($.if_clause, repeat($.elseif_clause), optional($.else_clause), $.endif_clause),

    while_clause: ($) => seq($.while, $.condition, optional($.body)),
    endwhile_clause: ($) => seq($.endwhile, $.condition),
    while_statement: ($) => seq($.while_clause, $.endwhile_clause),

    foreach_clause: ($) => seq($.foreach, $.condition, optional($.body)), /// TODO: change condition to iteration and define iteration
    endforeach_clause: ($) => seq($.endforeach, $.condition), /// TODO: change condition to iteration and define iteration
    foreach_statement: ($) => seq($.foreach_clause, $.endforeach_clause),

    arguments: ($) => repeat1($._untrimmed_argument),

    function_header: ($) => seq($.function, "(", $.identifier, optional($.arguments), ")"),
    endfunction_clause: ($) => seq($.endfunction, "(", optional($.arguments), ")"),
    function_definition: ($) => seq($.function_header, optional($.body), $.endfunction_clause),

    macro_header: ($) => seq($.macro, "(", $.identifier, optional($.arguments), ")"),
    endmacro_clause: ($) => seq($.endmacro, "(", optional($.arguments), ")"),
    macro_definition: ($) => seq($.macro_header, optional($.body), $.endmacro_clause),

    block_header: ($) => seq($.block, "(", optional($.arguments), ")"),
    endblock_clause: ($) => seq($.endblock, "(", optional($.arguments), ")"),
    block_definition: ($) => seq($.block_header, optional($.body), $.endblock_clause),

    normal_command: ($) => seq($.identifier, "(", optional($.arguments), ")"),

    _command_invocation: ($) =>
      choice(
        $.normal_command,
        $.if_statement,
        $.foreach_statement,
        $.while_statement,
        $.function_definition,
        $.macro_definition,
        $.block_definition
      ),

    skip_evaluation: ($) => seq(alias(/@/, "skip_symb"), $.skip_content),
    skip_content: ($) => /[^\n\r]*/,
    _statement: ($) => choice($.bracket_comment, $.line_comment, $._command_invocation, $.skip_evaluation),

    ...ruleNames(...keywords),
    identifier: ($) => choice($.variable_ref, /[A-Za-z_][A-Za-z0-9_]*/),
    integer: (_) => /[+-]*\d+/,
  },
});

function iregex(s) {
  return new RegExp(Array.from(s).reduce((acc, value) => acc + `[${value.toLowerCase()}${value.toUpperCase()}]`, ""));
}

function ruleName(name) {
  return { [name.replaceAll(/ /g, "_")]: (_) => iregex(name) };
}

function ruleNames(...names) {
  return Object.assign({}, ...names.map(ruleName));
}
function space() {
  return repeat(choice(/[\t]/, /[ ]/));
}
