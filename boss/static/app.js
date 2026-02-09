(() => {
  var __create = Object.create;
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __getProtoOf = Object.getPrototypeOf;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __commonJS = (cb, mod) => function __require() {
    return mod || (0, cb[__getOwnPropNames(cb)[0]])((mod = { exports: {} }).exports, mod), mod.exports;
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key2 of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key2) && key2 !== except)
          __defProp(to, key2, { get: () => from[key2], enumerable: !(desc = __getOwnPropDesc(from, key2)) || desc.enumerable });
    }
    return to;
  };
  var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
    // If the importer is in node compatibility mode or this is not an ESM
    // file that has been converted to a CommonJS file using a Babel-
    // compatible transform (i.e. "__esModule" has not been set), then set
    // "default" to the CommonJS "module.exports" for node compatibility.
    isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
    mod
  ));

  // node_modules/@profoundlogic/hogan/lib/compiler.js
  var require_compiler = __commonJS({
    "node_modules/@profoundlogic/hogan/lib/compiler.js"(exports) {
      (function(Hogan4) {
        var rIsWhitespace = /\S/, rQuot = /\"/g, rNewline = /\n/g, rCr = /\r/g, rSlash = /\\/g, rLineSep = /\u2028/, rParagraphSep = /\u2029/;
        Hogan4.tags = {
          "#": 1,
          "^": 2,
          "<": 3,
          "$": 4,
          "/": 5,
          "!": 6,
          ">": 7,
          "=": 8,
          "_v": 9,
          "{": 10,
          "&": 11,
          "_t": 12
        };
        Hogan4.scan = function scan(text, delimiters) {
          var len = text.length, IN_TEXT = 0, IN_TAG_TYPE = 1, IN_TAG = 2, state = IN_TEXT, tagType = null, tag = null, buf = "", tokens = [], seenTag = false, i = 0, lineStart = 0, otag = "{{", ctag = "}}";
          function addBuf() {
            if (buf.length > 0) {
              tokens.push({ tag: "_t", text: new String(buf) });
              buf = "";
            }
          }
          function lineIsWhitespace() {
            var isAllWhitespace = true;
            for (var j = lineStart; j < tokens.length; j++) {
              isAllWhitespace = Hogan4.tags[tokens[j].tag] < Hogan4.tags["_v"] || tokens[j].tag == "_t" && tokens[j].text.match(rIsWhitespace) === null;
              if (!isAllWhitespace) {
                return false;
              }
            }
            return isAllWhitespace;
          }
          function filterLine(haveSeenTag, noNewLine) {
            addBuf();
            if (haveSeenTag && lineIsWhitespace()) {
              for (var j = lineStart, next; j < tokens.length; j++) {
                if (tokens[j].text) {
                  if ((next = tokens[j + 1]) && next.tag == ">") {
                    next.indent = tokens[j].text.toString();
                  }
                  tokens.splice(j, 1);
                }
              }
            } else if (!noNewLine) {
              tokens.push({ tag: "\n" });
            }
            seenTag = false;
            lineStart = tokens.length;
          }
          function changeDelimiters(text2, index) {
            var close = "=" + ctag, closeIndex = text2.indexOf(close, index), delimiters2 = trim(
              text2.substring(text2.indexOf("=", index) + 1, closeIndex)
            ).split(" ");
            otag = delimiters2[0];
            ctag = delimiters2[delimiters2.length - 1];
            return closeIndex + close.length - 1;
          }
          if (delimiters) {
            delimiters = delimiters.split(" ");
            otag = delimiters[0];
            ctag = delimiters[1];
          }
          for (i = 0; i < len; i++) {
            if (state == IN_TEXT) {
              if (tagChange(otag, text, i)) {
                --i;
                addBuf();
                state = IN_TAG_TYPE;
              } else {
                if (text.charAt(i) == "\n") {
                  filterLine(seenTag);
                } else {
                  buf += text.charAt(i);
                }
              }
            } else if (state == IN_TAG_TYPE) {
              i += otag.length - 1;
              tag = Hogan4.tags[text.charAt(i + 1)];
              tagType = tag ? text.charAt(i + 1) : "_v";
              if (tagType == "=") {
                i = changeDelimiters(text, i);
                state = IN_TEXT;
              } else {
                if (tag) {
                  i++;
                }
                state = IN_TAG;
              }
              seenTag = i;
            } else {
              if (tagChange(ctag, text, i)) {
                tokens.push({
                  tag: tagType,
                  n: trim(buf),
                  otag,
                  ctag,
                  i: tagType == "/" ? seenTag - otag.length : i + ctag.length
                });
                buf = "";
                i += ctag.length - 1;
                state = IN_TEXT;
                if (tagType == "{") {
                  if (ctag == "}}") {
                    i++;
                  } else {
                    cleanTripleStache(tokens[tokens.length - 1]);
                  }
                }
              } else {
                buf += text.charAt(i);
              }
            }
          }
          filterLine(seenTag, true);
          return tokens;
        };
        function cleanTripleStache(token) {
          if (token.n.substr(token.n.length - 1) === "}") {
            token.n = token.n.substring(0, token.n.length - 1);
          }
        }
        function trim(s) {
          if (s.trim) {
            return s.trim();
          }
          return s.replace(/^\s*|\s*$/g, "");
        }
        function tagChange(tag, text, index) {
          if (text.charAt(index) != tag.charAt(0)) {
            return false;
          }
          for (var i = 1, l = tag.length; i < l; i++) {
            if (text.charAt(index + i) != tag.charAt(i)) {
              return false;
            }
          }
          return true;
        }
        var allowedInSuper = { "_t": true, "\n": true, "$": true, "/": true };
        function buildTree(tokens, kind, stack, customTags) {
          var instructions = [], opener = null, tail = null, token = null;
          tail = stack[stack.length - 1];
          while (tokens.length > 0) {
            token = tokens.shift();
            if (tail && tail.tag == "<" && !(token.tag in allowedInSuper)) {
              throw new Error("Illegal content in < super tag.");
            }
            if (Hogan4.tags[token.tag] <= Hogan4.tags["$"] || isOpener(token, customTags)) {
              stack.push(token);
              token.nodes = buildTree(tokens, token.tag, stack, customTags);
            } else if (token.tag == "/") {
              if (stack.length === 0) {
                throw new Error("Closing tag without opener: /" + token.n);
              }
              opener = stack.pop();
              if (token.n != opener.n && !isCloser(token.n, opener.n, customTags)) {
                throw new Error("Nesting error: " + opener.n + " vs. " + token.n);
              }
              opener.end = token.i;
              return instructions;
            } else if (token.tag == "\n") {
              token.last = tokens.length == 0 || tokens[0].tag == "\n";
            }
            instructions.push(token);
          }
          if (stack.length > 0) {
            throw new Error("missing closing tag: " + stack.pop().n);
          }
          return instructions;
        }
        function isOpener(token, tags) {
          for (var i = 0, l = tags.length; i < l; i++) {
            if (tags[i].o == token.n) {
              token.tag = "#";
              return true;
            }
          }
        }
        function isCloser(close, open, tags) {
          for (var i = 0, l = tags.length; i < l; i++) {
            if (tags[i].c == close && tags[i].o == open) {
              return true;
            }
          }
        }
        function stringifySubstitutions(obj) {
          var items = [];
          for (var key2 in obj) {
            items.push('"' + esc2(key2) + '": function(c,p,t,i) {' + obj[key2] + "}");
          }
          return "{ " + items.join(",") + " }";
        }
        function stringifyPartials(codeObj) {
          var partials = [];
          for (var key2 in codeObj.partials) {
            partials.push('"' + esc2(key2) + '":{name:"' + esc2(codeObj.partials[key2].name) + '", ' + stringifyPartials(codeObj.partials[key2]) + "}");
          }
          return "partials: {" + partials.join(",") + "}, subs: " + stringifySubstitutions(codeObj.subs);
        }
        Hogan4.stringify = function(codeObj, text, options) {
          return "{code: function (c,p,i) { " + Hogan4.wrapMain(codeObj.code) + " }," + stringifyPartials(codeObj) + "}";
        };
        var serialNo = 0;
        Hogan4.generate = function(tree, text, options) {
          serialNo = 0;
          var context = { code: "", subs: {}, partials: {} };
          Hogan4.walk(tree, context);
          if (options.asString) {
            return this.stringify(context, text, options);
          }
          return this.makeTemplate(context, text, options);
        };
        Hogan4.wrapMain = function(code) {
          return 'var t=this;t.b(i=i||"");' + code + "return t.fl();";
        };
        Hogan4.template = Hogan4.Template;
        Hogan4.makeTemplate = function(codeObj, text, options) {
          var template = this.makePartials(codeObj);
          template.code = new Function("c", "p", "i", this.wrapMain(codeObj.code));
          return new this.template(template, text, this, options);
        };
        Hogan4.makePartials = function(codeObj) {
          var key2, template = { subs: {}, partials: codeObj.partials, name: codeObj.name };
          for (key2 in template.partials) {
            template.partials[key2] = this.makePartials(template.partials[key2]);
          }
          for (key2 in codeObj.subs) {
            template.subs[key2] = new Function("c", "p", "t", "i", codeObj.subs[key2]);
          }
          return template;
        };
        function esc2(s) {
          return s.replace(rSlash, "\\\\").replace(rQuot, '\\"').replace(rNewline, "\\n").replace(rCr, "\\r").replace(rLineSep, "\\u2028").replace(rParagraphSep, "\\u2029");
        }
        function chooseMethod(s) {
          return ~s.indexOf(".") ? "d" : "f";
        }
        function createPartial(node, context) {
          var prefix = "<" + (context.prefix || "");
          var sym = prefix + node.n + serialNo++;
          context.partials[sym] = { name: node.n, partials: {} };
          context.code += 't.b(t.rp("' + esc2(sym) + '",c,p,"' + (node.indent || "") + '"));';
          return sym;
        }
        Hogan4.codegen = {
          "#": function(node, context) {
            context.code += "if(t.s(t." + chooseMethod(node.n) + '("' + esc2(node.n) + '",c,p,1),c,p,0,' + node.i + "," + node.end + ',"' + node.otag + " " + node.ctag + '")){t.rs(c,p,function(c,p,t){';
            Hogan4.walk(node.nodes, context);
            context.code += "});c.pop();}";
          },
          "^": function(node, context) {
            context.code += "if(!t.s(t." + chooseMethod(node.n) + '("' + esc2(node.n) + '",c,p,1),c,p,1,0,0,"")){';
            Hogan4.walk(node.nodes, context);
            context.code += "};";
          },
          ">": createPartial,
          "<": function(node, context) {
            var ctx = { partials: {}, code: "", subs: {}, inPartial: true };
            Hogan4.walk(node.nodes, ctx);
            var template = context.partials[createPartial(node, context)];
            template.subs = ctx.subs;
            template.partials = ctx.partials;
          },
          "$": function(node, context) {
            var ctx = { subs: {}, code: "", partials: context.partials, prefix: node.n };
            Hogan4.walk(node.nodes, ctx);
            context.subs[node.n] = ctx.code;
            if (!context.inPartial) {
              context.code += 't.sub("' + esc2(node.n) + '",c,p,i);';
            }
          },
          "\n": function(node, context) {
            context.code += write('"\\n"' + (node.last ? "" : " + i"));
          },
          "_v": function(node, context) {
            context.code += "t.b(t.v(t." + chooseMethod(node.n) + '("' + esc2(node.n) + '",c,p,0)));';
          },
          "_t": function(node, context) {
            context.code += write('"' + esc2(node.text) + '"');
          },
          "{": tripleStache,
          "&": tripleStache
        };
        function tripleStache(node, context) {
          context.code += "t.b(t.t(t." + chooseMethod(node.n) + '("' + esc2(node.n) + '",c,p,0)));';
        }
        function write(s) {
          return "t.b(" + s + ");";
        }
        Hogan4.walk = function(nodelist, context) {
          var func;
          for (var i = 0, l = nodelist.length; i < l; i++) {
            func = Hogan4.codegen[nodelist[i].tag];
            func && func(nodelist[i], context);
          }
          return context;
        };
        Hogan4.parse = function(tokens, text, options) {
          options = options || {};
          return buildTree(tokens, "", [], options.sectionTags || []);
        };
        Hogan4.cache = {};
        Hogan4.cacheKey = function(text, options) {
          return [text, !!options.asString, !!options.disableLambda, options.delimiters, !!options.modelGet].join("||");
        };
        Hogan4.compile = function(text, options) {
          options = options || {};
          var key2 = Hogan4.cacheKey(text, options);
          var template = this.cache[key2];
          if (template) {
            var partials = template.partials;
            for (var name in partials) {
              delete partials[name].instance;
            }
            return template;
          }
          template = this.generate(this.parse(this.scan(text, options.delimiters), text, options), text, options);
          return this.cache[key2] = template;
        };
      })(typeof exports !== "undefined" ? exports : Hogan);
    }
  });

  // node_modules/@profoundlogic/hogan/lib/template.js
  var require_template = __commonJS({
    "node_modules/@profoundlogic/hogan/lib/template.js"(exports) {
      var Hogan4 = {};
      (function(Hogan5) {
        Hogan5.Template = function(codeObj, text, compiler, options) {
          codeObj = codeObj || {};
          this.r = codeObj.code || this.r;
          this.c = compiler;
          this.options = options || {};
          this.text = text || "";
          this.partials = codeObj.partials || {};
          this.subs = codeObj.subs || {};
          this.buf = "";
        };
        Hogan5.Template.prototype = {
          // render: replaced by generated code.
          r: function(context, partials, indent) {
            return "";
          },
          // variable escaping
          v: hoganEscape,
          // triple stache
          t: coerceToString,
          render: function render(context, partials, indent) {
            return this.ri([context], partials || {}, indent);
          },
          // render internal -- a hook for overrides that catches partials too
          ri: function(context, partials, indent) {
            return this.r(context, partials, indent);
          },
          // ensurePartial
          ep: function(symbol, partials) {
            var partial = this.partials[symbol];
            var template = partials[partial.name];
            if (partial.instance && partial.base == template) {
              return partial.instance;
            }
            if (typeof template == "string") {
              if (!this.c) {
                throw new Error("No compiler available.");
              }
              template = this.c.compile(template, this.options);
            }
            if (!template) {
              return null;
            }
            this.partials[symbol].base = template;
            if (partial.subs) {
              if (!partials.stackText) partials.stackText = {};
              for (key in partial.subs) {
                if (!partials.stackText[key]) {
                  partials.stackText[key] = this.activeSub !== void 0 && partials.stackText[this.activeSub] ? partials.stackText[this.activeSub] : this.text;
                }
              }
              template = createSpecializedPartial(
                template,
                partial.subs,
                partial.partials,
                this.stackSubs,
                this.stackPartials,
                partials.stackText
              );
            }
            this.partials[symbol].instance = template;
            return template;
          },
          // tries to find a partial in the current scope and render it
          rp: function(symbol, context, partials, indent) {
            var partial = this.ep(symbol, partials);
            if (!partial) {
              return "";
            }
            return partial.ri(context, partials, indent);
          },
          // render a section
          rs: function(context, partials, section) {
            var tail = context[context.length - 1];
            if (!isArray(tail)) {
              section(context, partials, this);
              return;
            }
            for (var i = 0; i < tail.length; i++) {
              context.push(tail[i]);
              section(context, partials, this);
              context.pop();
            }
          },
          // maybe start a section
          s: function(val, ctx, partials, inverted, start, end, tags) {
            var pass;
            if (isArray(val) && val.length === 0) {
              return false;
            }
            if (typeof val == "function") {
              val = this.ms(val, ctx, partials, inverted, start, end, tags);
            }
            pass = !!val;
            if (!inverted && pass && ctx) {
              ctx.push(typeof val == "object" ? val : ctx[ctx.length - 1]);
            }
            return pass;
          },
          // find values with dotted names
          d: function(key2, ctx, partials, returnFound) {
            var found, names = key2.split("."), val = this.f(names[0], ctx, partials, returnFound), doModelGet = this.options.modelGet, cx = null;
            if (key2 === "." && isArray(ctx[ctx.length - 2])) {
              val = ctx[ctx.length - 1];
            } else {
              for (var i = 1; i < names.length; i++) {
                found = findInScope(names[i], val, doModelGet);
                if (found !== void 0) {
                  cx = val;
                  val = found;
                } else {
                  val = "";
                }
              }
            }
            if (returnFound && !val) {
              return false;
            }
            if (!returnFound && typeof val == "function") {
              ctx.push(cx);
              val = this.mv(val, ctx, partials);
              ctx.pop();
            }
            return val;
          },
          // find values with normal names
          f: function(key2, ctx, partials, returnFound) {
            var val = false, v = null, found = false, doModelGet = this.options.modelGet;
            for (var i = ctx.length - 1; i >= 0; i--) {
              v = ctx[i];
              val = findInScope(key2, v, doModelGet);
              if (val !== void 0) {
                found = true;
                break;
              }
            }
            if (!found) {
              return returnFound ? false : "";
            }
            if (!returnFound && typeof val == "function") {
              val = this.mv(val, ctx, partials);
            }
            return val;
          },
          // higher order templates
          ls: function(func, cx, ctx, partials, text, tags) {
            var oldTags = this.options.delimiters;
            this.options.delimiters = tags;
            this.b(this.ct(coerceToString(func.call(cx, text, ctx)), cx, partials));
            this.options.delimiters = oldTags;
            return false;
          },
          // compile text
          ct: function(text, cx, partials) {
            if (this.options.disableLambda) {
              throw new Error("Lambda features disabled.");
            }
            return this.c.compile(text, this.options).render(cx, partials);
          },
          // template result buffering
          b: function(s) {
            this.buf += s;
          },
          fl: function() {
            var r = this.buf;
            this.buf = "";
            return r;
          },
          // method replace section
          ms: function(func, ctx, partials, inverted, start, end, tags) {
            var textSource, cx = ctx[ctx.length - 1], result = func.call(cx);
            if (typeof result == "function") {
              if (inverted) {
                return true;
              } else {
                textSource = this.activeSub && this.subsText && this.subsText[this.activeSub] ? this.subsText[this.activeSub] : this.text;
                return this.ls(result, cx, ctx, partials, textSource.substring(start, end), tags);
              }
            }
            return result;
          },
          // method replace variable
          mv: function(func, ctx, partials) {
            var cx = ctx[ctx.length - 1];
            var result = func.call(cx);
            if (typeof result == "function") {
              return this.ct(coerceToString(result.call(cx)), cx, partials);
            }
            return result;
          },
          sub: function(name, context, partials, indent) {
            var f = this.subs[name];
            if (f) {
              this.activeSub = name;
              f(context, partials, this, indent);
              this.activeSub = false;
            }
          }
        };
        function findInScope(key2, scope, doModelGet) {
          var val;
          if (scope && typeof scope == "object") {
            if (scope[key2] !== void 0) {
              val = scope[key2];
            } else if (doModelGet && scope.get && typeof scope.get == "function") {
              val = scope.get(key2);
            }
          }
          return val;
        }
        function createSpecializedPartial(instance, subs, partials, stackSubs, stackPartials, stackText) {
          function PartialTemplate() {
          }
          ;
          PartialTemplate.prototype = instance;
          function Substitutions() {
          }
          ;
          Substitutions.prototype = instance.subs;
          var key2;
          var partial = new PartialTemplate();
          partial.subs = new Substitutions();
          partial.subsText = {};
          partial.buf = "";
          stackSubs = stackSubs || {};
          partial.stackSubs = stackSubs;
          partial.subsText = stackText;
          for (key2 in subs) {
            if (!stackSubs[key2]) stackSubs[key2] = subs[key2];
          }
          for (key2 in stackSubs) {
            partial.subs[key2] = stackSubs[key2];
          }
          stackPartials = stackPartials || {};
          partial.stackPartials = stackPartials;
          for (key2 in partials) {
            if (!stackPartials[key2]) stackPartials[key2] = partials[key2];
          }
          for (key2 in stackPartials) {
            partial.partials[key2] = stackPartials[key2];
          }
          return partial;
        }
        var rAmp = /&/g, rLt = /</g, rGt = />/g, rApos = /\'/g, rQuot = /\"/g, hChars = /[&<>\"\']/;
        function coerceToString(val) {
          return String(val === null || val === void 0 ? "" : val);
        }
        function hoganEscape(str) {
          str = coerceToString(str);
          return hChars.test(str) ? str.replace(rAmp, "&amp;").replace(rLt, "&lt;").replace(rGt, "&gt;").replace(rApos, "&#39;").replace(rQuot, "&quot;") : str;
        }
        var isArray = Array.isArray || function(a) {
          return Object.prototype.toString.call(a) === "[object Array]";
        };
      })(typeof exports !== "undefined" ? exports : Hogan4);
    }
  });

  // node_modules/@profoundlogic/hogan/lib/hogan.js
  var require_hogan = __commonJS({
    "node_modules/@profoundlogic/hogan/lib/hogan.js"(exports, module) {
      var Hogan4 = require_compiler();
      Hogan4.Template = require_template().Template;
      Hogan4.template = Hogan4.Template;
      module.exports = Hogan4;
    }
  });

  // node_modules/diff2html/lib-esm/types.js
  var LineType;
  (function(LineType2) {
    LineType2["INSERT"] = "insert";
    LineType2["DELETE"] = "delete";
    LineType2["CONTEXT"] = "context";
  })(LineType || (LineType = {}));
  var OutputFormatType = {
    LINE_BY_LINE: "line-by-line",
    SIDE_BY_SIDE: "side-by-side"
  };
  var LineMatchingType = {
    LINES: "lines",
    WORDS: "words",
    NONE: "none"
  };
  var DiffStyleType = {
    WORD: "word",
    CHAR: "char"
  };
  var ColorSchemeType;
  (function(ColorSchemeType2) {
    ColorSchemeType2["AUTO"] = "auto";
    ColorSchemeType2["DARK"] = "dark";
    ColorSchemeType2["LIGHT"] = "light";
  })(ColorSchemeType || (ColorSchemeType = {}));

  // node_modules/diff2html/lib-esm/utils.js
  var specials = [
    "-",
    "[",
    "]",
    "/",
    "{",
    "}",
    "(",
    ")",
    "*",
    "+",
    "?",
    ".",
    "\\",
    "^",
    "$",
    "|"
  ];
  var regex = RegExp("[" + specials.join("\\") + "]", "g");
  function escapeForRegExp(str) {
    return str.replace(regex, "\\$&");
  }
  function unifyPath(path) {
    return path ? path.replace(/\\/g, "/") : path;
  }
  function hashCode(text) {
    let i, chr, len;
    let hash = 0;
    for (i = 0, len = text.length; i < len; i++) {
      chr = text.charCodeAt(i);
      hash = (hash << 5) - hash + chr;
      hash |= 0;
    }
    return hash;
  }
  function max(arr) {
    const length = arr.length;
    let max2 = -Infinity;
    for (let i = 0; i < length; i++) {
      max2 = Math.max(max2, arr[i]);
    }
    return max2;
  }

  // node_modules/diff2html/lib-esm/diff-parser.js
  function getExtension(filename, language) {
    const filenameParts = filename.split(".");
    return filenameParts.length > 1 ? filenameParts[filenameParts.length - 1] : language;
  }
  function startsWithAny(str, prefixes) {
    return prefixes.reduce((startsWith, prefix) => startsWith || str.startsWith(prefix), false);
  }
  var baseDiffFilenamePrefixes = ["a/", "b/", "i/", "w/", "c/", "o/"];
  function getFilename(line, linePrefix, extraPrefix) {
    const prefixes = extraPrefix !== void 0 ? [...baseDiffFilenamePrefixes, extraPrefix] : baseDiffFilenamePrefixes;
    const FilenameRegExp = linePrefix ? new RegExp(`^${escapeForRegExp(linePrefix)} "?(.+?)"?$`) : new RegExp('^"?(.+?)"?$');
    const [, filename = ""] = FilenameRegExp.exec(line) || [];
    const matchingPrefix = prefixes.find((p) => filename.indexOf(p) === 0);
    const fnameWithoutPrefix = matchingPrefix ? filename.slice(matchingPrefix.length) : filename;
    return fnameWithoutPrefix.replace(/\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)? [+-]\d{4}.*$/, "");
  }
  function getSrcFilename(line, srcPrefix) {
    return getFilename(line, "---", srcPrefix);
  }
  function getDstFilename(line, dstPrefix) {
    return getFilename(line, "+++", dstPrefix);
  }
  function parse(diffInput, config = {}) {
    const files = [];
    let currentFile = null;
    let currentBlock = null;
    let oldLine = null;
    let oldLine2 = null;
    let newLine = null;
    let possibleOldName = null;
    let possibleNewName = null;
    const oldFileNameHeader = "--- ";
    const newFileNameHeader = "+++ ";
    const hunkHeaderPrefix = "@@";
    const oldMode = /^old mode (\d{6})/;
    const newMode = /^new mode (\d{6})/;
    const deletedFileMode = /^deleted file mode (\d{6})/;
    const newFileMode = /^new file mode (\d{6})/;
    const copyFrom = /^copy from "?(.+)"?/;
    const copyTo = /^copy to "?(.+)"?/;
    const renameFrom = /^rename from "?(.+)"?/;
    const renameTo = /^rename to "?(.+)"?/;
    const similarityIndex = /^similarity index (\d+)%/;
    const dissimilarityIndex = /^dissimilarity index (\d+)%/;
    const index = /^index ([\da-z]+)\.\.([\da-z]+)\s*(\d{6})?/;
    const binaryFiles = /^Binary files (.*) and (.*) differ/;
    const binaryDiff = /^GIT binary patch/;
    const combinedIndex = /^index ([\da-z]+),([\da-z]+)\.\.([\da-z]+)/;
    const combinedMode = /^mode (\d{6}),(\d{6})\.\.(\d{6})/;
    const combinedNewFile = /^new file mode (\d{6})/;
    const combinedDeletedFile = /^deleted file mode (\d{6}),(\d{6})/;
    const diffLines = diffInput.replace(/\\ No newline at end of file/g, "").replace(/\r\n?/g, "\n").split("\n");
    function saveBlock() {
      if (currentBlock !== null && currentFile !== null) {
        currentFile.blocks.push(currentBlock);
        currentBlock = null;
      }
    }
    function saveFile() {
      if (currentFile !== null) {
        if (!currentFile.oldName && possibleOldName !== null) {
          currentFile.oldName = possibleOldName;
        }
        if (!currentFile.newName && possibleNewName !== null) {
          currentFile.newName = possibleNewName;
        }
        if (currentFile.newName) {
          files.push(currentFile);
          currentFile = null;
        }
      }
      possibleOldName = null;
      possibleNewName = null;
    }
    function startFile() {
      saveBlock();
      saveFile();
      currentFile = {
        blocks: [],
        deletedLines: 0,
        addedLines: 0
      };
    }
    function startBlock(line) {
      saveBlock();
      let values;
      if (currentFile !== null) {
        if (values = /^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@.*/.exec(line)) {
          currentFile.isCombined = false;
          oldLine = parseInt(values[1], 10);
          newLine = parseInt(values[2], 10);
        } else if (values = /^@@@ -(\d+)(?:,\d+)? -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@@.*/.exec(line)) {
          currentFile.isCombined = true;
          oldLine = parseInt(values[1], 10);
          oldLine2 = parseInt(values[2], 10);
          newLine = parseInt(values[3], 10);
        } else {
          if (line.startsWith(hunkHeaderPrefix)) {
            console.error("Failed to parse lines, starting in 0!");
          }
          oldLine = 0;
          newLine = 0;
          currentFile.isCombined = false;
        }
      }
      currentBlock = {
        lines: [],
        oldStartLine: oldLine,
        oldStartLine2: oldLine2,
        newStartLine: newLine,
        header: line
      };
    }
    function createLine(line) {
      if (currentFile === null || currentBlock === null || oldLine === null || newLine === null)
        return;
      const currentLine = {
        content: line
      };
      const addedPrefixes = currentFile.isCombined ? ["+ ", " +", "++"] : ["+"];
      const deletedPrefixes = currentFile.isCombined ? ["- ", " -", "--"] : ["-"];
      if (startsWithAny(line, addedPrefixes)) {
        currentFile.addedLines++;
        currentLine.type = LineType.INSERT;
        currentLine.oldNumber = void 0;
        currentLine.newNumber = newLine++;
      } else if (startsWithAny(line, deletedPrefixes)) {
        currentFile.deletedLines++;
        currentLine.type = LineType.DELETE;
        currentLine.oldNumber = oldLine++;
        currentLine.newNumber = void 0;
      } else {
        currentLine.type = LineType.CONTEXT;
        currentLine.oldNumber = oldLine++;
        currentLine.newNumber = newLine++;
      }
      currentBlock.lines.push(currentLine);
    }
    function existHunkHeader(line, lineIdx) {
      let idx = lineIdx;
      while (idx < diffLines.length - 3) {
        if (line.startsWith("diff")) {
          return false;
        }
        if (diffLines[idx].startsWith(oldFileNameHeader) && diffLines[idx + 1].startsWith(newFileNameHeader) && diffLines[idx + 2].startsWith(hunkHeaderPrefix)) {
          return true;
        }
        idx++;
      }
      return false;
    }
    diffLines.forEach((line, lineIndex) => {
      if (!line || line.startsWith("*")) {
        return;
      }
      let values;
      const prevLine = diffLines[lineIndex - 1];
      const nxtLine = diffLines[lineIndex + 1];
      const afterNxtLine = diffLines[lineIndex + 2];
      if (line.startsWith("diff --git") || line.startsWith("diff --combined")) {
        startFile();
        const gitDiffStart = /^diff --git "?([a-ciow]\/.+)"? "?([a-ciow]\/.+)"?/;
        if (values = gitDiffStart.exec(line)) {
          possibleOldName = getFilename(values[1], void 0, config.dstPrefix);
          possibleNewName = getFilename(values[2], void 0, config.srcPrefix);
        }
        if (currentFile === null) {
          throw new Error("Where is my file !!!");
        }
        currentFile.isGitDiff = true;
        return;
      }
      if (line.startsWith("Binary files") && !(currentFile === null || currentFile === void 0 ? void 0 : currentFile.isGitDiff)) {
        startFile();
        const unixDiffBinaryStart = /^Binary files "?([a-ciow]\/.+)"? and "?([a-ciow]\/.+)"? differ/;
        if (values = unixDiffBinaryStart.exec(line)) {
          possibleOldName = getFilename(values[1], void 0, config.dstPrefix);
          possibleNewName = getFilename(values[2], void 0, config.srcPrefix);
        }
        if (currentFile === null) {
          throw new Error("Where is my file !!!");
        }
        currentFile.isBinary = true;
        return;
      }
      if (!currentFile || !currentFile.isGitDiff && currentFile && line.startsWith(oldFileNameHeader) && nxtLine.startsWith(newFileNameHeader) && afterNxtLine.startsWith(hunkHeaderPrefix)) {
        startFile();
      }
      if (currentFile === null || currentFile === void 0 ? void 0 : currentFile.isTooBig) {
        return;
      }
      if (currentFile && (typeof config.diffMaxChanges === "number" && currentFile.addedLines + currentFile.deletedLines > config.diffMaxChanges || typeof config.diffMaxLineLength === "number" && line.length > config.diffMaxLineLength)) {
        currentFile.isTooBig = true;
        currentFile.addedLines = 0;
        currentFile.deletedLines = 0;
        currentFile.blocks = [];
        currentBlock = null;
        const message = typeof config.diffTooBigMessage === "function" ? config.diffTooBigMessage(files.length) : "Diff too big to be displayed";
        startBlock(message);
        return;
      }
      if (line.startsWith(oldFileNameHeader) && nxtLine.startsWith(newFileNameHeader) || line.startsWith(newFileNameHeader) && prevLine.startsWith(oldFileNameHeader)) {
        if (currentFile && !currentFile.oldName && line.startsWith("--- ") && (values = getSrcFilename(line, config.srcPrefix))) {
          currentFile.oldName = values;
          currentFile.language = getExtension(currentFile.oldName, currentFile.language);
          return;
        }
        if (currentFile && !currentFile.newName && line.startsWith("+++ ") && (values = getDstFilename(line, config.dstPrefix))) {
          currentFile.newName = values;
          currentFile.language = getExtension(currentFile.newName, currentFile.language);
          return;
        }
      }
      if (currentFile && (line.startsWith(hunkHeaderPrefix) || currentFile.isGitDiff && currentFile.oldName && currentFile.newName && !currentBlock)) {
        startBlock(line);
        return;
      }
      if (currentBlock && (line.startsWith("+") || line.startsWith("-") || line.startsWith(" "))) {
        createLine(line);
        return;
      }
      const doesNotExistHunkHeader = !existHunkHeader(line, lineIndex);
      if (currentFile === null) {
        throw new Error("Where is my file !!!");
      }
      if (values = oldMode.exec(line)) {
        currentFile.oldMode = values[1];
      } else if (values = newMode.exec(line)) {
        currentFile.newMode = values[1];
      } else if (values = deletedFileMode.exec(line)) {
        currentFile.deletedFileMode = values[1];
        currentFile.isDeleted = true;
      } else if (values = newFileMode.exec(line)) {
        currentFile.newFileMode = values[1];
        currentFile.isNew = true;
      } else if (values = copyFrom.exec(line)) {
        if (doesNotExistHunkHeader) {
          currentFile.oldName = values[1];
        }
        currentFile.isCopy = true;
      } else if (values = copyTo.exec(line)) {
        if (doesNotExistHunkHeader) {
          currentFile.newName = values[1];
        }
        currentFile.isCopy = true;
      } else if (values = renameFrom.exec(line)) {
        if (doesNotExistHunkHeader) {
          currentFile.oldName = values[1];
        }
        currentFile.isRename = true;
      } else if (values = renameTo.exec(line)) {
        if (doesNotExistHunkHeader) {
          currentFile.newName = values[1];
        }
        currentFile.isRename = true;
      } else if (values = binaryFiles.exec(line)) {
        currentFile.isBinary = true;
        currentFile.oldName = getFilename(values[1], void 0, config.srcPrefix);
        currentFile.newName = getFilename(values[2], void 0, config.dstPrefix);
        startBlock("Binary file");
      } else if (binaryDiff.test(line)) {
        currentFile.isBinary = true;
        startBlock(line);
      } else if (values = similarityIndex.exec(line)) {
        currentFile.unchangedPercentage = parseInt(values[1], 10);
      } else if (values = dissimilarityIndex.exec(line)) {
        currentFile.changedPercentage = parseInt(values[1], 10);
      } else if (values = index.exec(line)) {
        currentFile.checksumBefore = values[1];
        currentFile.checksumAfter = values[2];
        if (values[3])
          currentFile.mode = values[3];
      } else if (values = combinedIndex.exec(line)) {
        currentFile.checksumBefore = [values[2], values[3]];
        currentFile.checksumAfter = values[1];
      } else if (values = combinedMode.exec(line)) {
        currentFile.oldMode = [values[2], values[3]];
        currentFile.newMode = values[1];
      } else if (values = combinedNewFile.exec(line)) {
        currentFile.newFileMode = values[1];
        currentFile.isNew = true;
      } else if (values = combinedDeletedFile.exec(line)) {
        currentFile.deletedFileMode = values[1];
        currentFile.isDeleted = true;
      }
    });
    saveBlock();
    saveFile();
    return files;
  }

  // node_modules/diff/libesm/diff/base.js
  var Diff = class {
    diff(oldStr, newStr, options = {}) {
      let callback;
      if (typeof options === "function") {
        callback = options;
        options = {};
      } else if ("callback" in options) {
        callback = options.callback;
      }
      const oldString = this.castInput(oldStr, options);
      const newString = this.castInput(newStr, options);
      const oldTokens = this.removeEmpty(this.tokenize(oldString, options));
      const newTokens = this.removeEmpty(this.tokenize(newString, options));
      return this.diffWithOptionsObj(oldTokens, newTokens, options, callback);
    }
    diffWithOptionsObj(oldTokens, newTokens, options, callback) {
      var _a;
      const done = (value) => {
        value = this.postProcess(value, options);
        if (callback) {
          setTimeout(function() {
            callback(value);
          }, 0);
          return void 0;
        } else {
          return value;
        }
      };
      const newLen = newTokens.length, oldLen = oldTokens.length;
      let editLength = 1;
      let maxEditLength = newLen + oldLen;
      if (options.maxEditLength != null) {
        maxEditLength = Math.min(maxEditLength, options.maxEditLength);
      }
      const maxExecutionTime = (_a = options.timeout) !== null && _a !== void 0 ? _a : Infinity;
      const abortAfterTimestamp = Date.now() + maxExecutionTime;
      const bestPath = [{ oldPos: -1, lastComponent: void 0 }];
      let newPos = this.extractCommon(bestPath[0], newTokens, oldTokens, 0, options);
      if (bestPath[0].oldPos + 1 >= oldLen && newPos + 1 >= newLen) {
        return done(this.buildValues(bestPath[0].lastComponent, newTokens, oldTokens));
      }
      let minDiagonalToConsider = -Infinity, maxDiagonalToConsider = Infinity;
      const execEditLength = () => {
        for (let diagonalPath = Math.max(minDiagonalToConsider, -editLength); diagonalPath <= Math.min(maxDiagonalToConsider, editLength); diagonalPath += 2) {
          let basePath;
          const removePath = bestPath[diagonalPath - 1], addPath = bestPath[diagonalPath + 1];
          if (removePath) {
            bestPath[diagonalPath - 1] = void 0;
          }
          let canAdd = false;
          if (addPath) {
            const addPathNewPos = addPath.oldPos - diagonalPath;
            canAdd = addPath && 0 <= addPathNewPos && addPathNewPos < newLen;
          }
          const canRemove = removePath && removePath.oldPos + 1 < oldLen;
          if (!canAdd && !canRemove) {
            bestPath[diagonalPath] = void 0;
            continue;
          }
          if (!canRemove || canAdd && removePath.oldPos < addPath.oldPos) {
            basePath = this.addToPath(addPath, true, false, 0, options);
          } else {
            basePath = this.addToPath(removePath, false, true, 1, options);
          }
          newPos = this.extractCommon(basePath, newTokens, oldTokens, diagonalPath, options);
          if (basePath.oldPos + 1 >= oldLen && newPos + 1 >= newLen) {
            return done(this.buildValues(basePath.lastComponent, newTokens, oldTokens)) || true;
          } else {
            bestPath[diagonalPath] = basePath;
            if (basePath.oldPos + 1 >= oldLen) {
              maxDiagonalToConsider = Math.min(maxDiagonalToConsider, diagonalPath - 1);
            }
            if (newPos + 1 >= newLen) {
              minDiagonalToConsider = Math.max(minDiagonalToConsider, diagonalPath + 1);
            }
          }
        }
        editLength++;
      };
      if (callback) {
        (function exec() {
          setTimeout(function() {
            if (editLength > maxEditLength || Date.now() > abortAfterTimestamp) {
              return callback(void 0);
            }
            if (!execEditLength()) {
              exec();
            }
          }, 0);
        })();
      } else {
        while (editLength <= maxEditLength && Date.now() <= abortAfterTimestamp) {
          const ret = execEditLength();
          if (ret) {
            return ret;
          }
        }
      }
    }
    addToPath(path, added, removed, oldPosInc, options) {
      const last = path.lastComponent;
      if (last && !options.oneChangePerToken && last.added === added && last.removed === removed) {
        return {
          oldPos: path.oldPos + oldPosInc,
          lastComponent: { count: last.count + 1, added, removed, previousComponent: last.previousComponent }
        };
      } else {
        return {
          oldPos: path.oldPos + oldPosInc,
          lastComponent: { count: 1, added, removed, previousComponent: last }
        };
      }
    }
    extractCommon(basePath, newTokens, oldTokens, diagonalPath, options) {
      const newLen = newTokens.length, oldLen = oldTokens.length;
      let oldPos = basePath.oldPos, newPos = oldPos - diagonalPath, commonCount = 0;
      while (newPos + 1 < newLen && oldPos + 1 < oldLen && this.equals(oldTokens[oldPos + 1], newTokens[newPos + 1], options)) {
        newPos++;
        oldPos++;
        commonCount++;
        if (options.oneChangePerToken) {
          basePath.lastComponent = { count: 1, previousComponent: basePath.lastComponent, added: false, removed: false };
        }
      }
      if (commonCount && !options.oneChangePerToken) {
        basePath.lastComponent = { count: commonCount, previousComponent: basePath.lastComponent, added: false, removed: false };
      }
      basePath.oldPos = oldPos;
      return newPos;
    }
    equals(left, right, options) {
      if (options.comparator) {
        return options.comparator(left, right);
      } else {
        return left === right || !!options.ignoreCase && left.toLowerCase() === right.toLowerCase();
      }
    }
    removeEmpty(array) {
      const ret = [];
      for (let i = 0; i < array.length; i++) {
        if (array[i]) {
          ret.push(array[i]);
        }
      }
      return ret;
    }
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    castInput(value, options) {
      return value;
    }
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    tokenize(value, options) {
      return Array.from(value);
    }
    join(chars) {
      return chars.join("");
    }
    postProcess(changeObjects, options) {
      return changeObjects;
    }
    get useLongestToken() {
      return false;
    }
    buildValues(lastComponent, newTokens, oldTokens) {
      const components = [];
      let nextComponent;
      while (lastComponent) {
        components.push(lastComponent);
        nextComponent = lastComponent.previousComponent;
        delete lastComponent.previousComponent;
        lastComponent = nextComponent;
      }
      components.reverse();
      const componentLen = components.length;
      let componentPos = 0, newPos = 0, oldPos = 0;
      for (; componentPos < componentLen; componentPos++) {
        const component = components[componentPos];
        if (!component.removed) {
          if (!component.added && this.useLongestToken) {
            let value = newTokens.slice(newPos, newPos + component.count);
            value = value.map(function(value2, i) {
              const oldValue = oldTokens[oldPos + i];
              return oldValue.length > value2.length ? oldValue : value2;
            });
            component.value = this.join(value);
          } else {
            component.value = this.join(newTokens.slice(newPos, newPos + component.count));
          }
          newPos += component.count;
          if (!component.added) {
            oldPos += component.count;
          }
        } else {
          component.value = this.join(oldTokens.slice(oldPos, oldPos + component.count));
          oldPos += component.count;
        }
      }
      return components;
    }
  };

  // node_modules/diff/libesm/diff/character.js
  var CharacterDiff = class extends Diff {
  };
  var characterDiff = new CharacterDiff();
  function diffChars(oldStr, newStr, options) {
    return characterDiff.diff(oldStr, newStr, options);
  }

  // node_modules/diff/libesm/util/string.js
  function longestCommonPrefix(str1, str2) {
    let i;
    for (i = 0; i < str1.length && i < str2.length; i++) {
      if (str1[i] != str2[i]) {
        return str1.slice(0, i);
      }
    }
    return str1.slice(0, i);
  }
  function longestCommonSuffix(str1, str2) {
    let i;
    if (!str1 || !str2 || str1[str1.length - 1] != str2[str2.length - 1]) {
      return "";
    }
    for (i = 0; i < str1.length && i < str2.length; i++) {
      if (str1[str1.length - (i + 1)] != str2[str2.length - (i + 1)]) {
        return str1.slice(-i);
      }
    }
    return str1.slice(-i);
  }
  function replacePrefix(string, oldPrefix, newPrefix) {
    if (string.slice(0, oldPrefix.length) != oldPrefix) {
      throw Error(`string ${JSON.stringify(string)} doesn't start with prefix ${JSON.stringify(oldPrefix)}; this is a bug`);
    }
    return newPrefix + string.slice(oldPrefix.length);
  }
  function replaceSuffix(string, oldSuffix, newSuffix) {
    if (!oldSuffix) {
      return string + newSuffix;
    }
    if (string.slice(-oldSuffix.length) != oldSuffix) {
      throw Error(`string ${JSON.stringify(string)} doesn't end with suffix ${JSON.stringify(oldSuffix)}; this is a bug`);
    }
    return string.slice(0, -oldSuffix.length) + newSuffix;
  }
  function removePrefix(string, oldPrefix) {
    return replacePrefix(string, oldPrefix, "");
  }
  function removeSuffix(string, oldSuffix) {
    return replaceSuffix(string, oldSuffix, "");
  }
  function maximumOverlap(string1, string2) {
    return string2.slice(0, overlapCount(string1, string2));
  }
  function overlapCount(a, b) {
    let startA = 0;
    if (a.length > b.length) {
      startA = a.length - b.length;
    }
    let endB = b.length;
    if (a.length < b.length) {
      endB = a.length;
    }
    const map = Array(endB);
    let k = 0;
    map[0] = 0;
    for (let j = 1; j < endB; j++) {
      if (b[j] == b[k]) {
        map[j] = map[k];
      } else {
        map[j] = k;
      }
      while (k > 0 && b[j] != b[k]) {
        k = map[k];
      }
      if (b[j] == b[k]) {
        k++;
      }
    }
    k = 0;
    for (let i = startA; i < a.length; i++) {
      while (k > 0 && a[i] != b[k]) {
        k = map[k];
      }
      if (a[i] == b[k]) {
        k++;
      }
    }
    return k;
  }
  function trailingWs(string) {
    let i;
    for (i = string.length - 1; i >= 0; i--) {
      if (!string[i].match(/\s/)) {
        break;
      }
    }
    return string.substring(i + 1);
  }
  function leadingWs(string) {
    const match = string.match(/^\s*/);
    return match ? match[0] : "";
  }

  // node_modules/diff/libesm/diff/word.js
  var extendedWordChars = "a-zA-Z0-9_\\u{AD}\\u{C0}-\\u{D6}\\u{D8}-\\u{F6}\\u{F8}-\\u{2C6}\\u{2C8}-\\u{2D7}\\u{2DE}-\\u{2FF}\\u{1E00}-\\u{1EFF}";
  var tokenizeIncludingWhitespace = new RegExp(`[${extendedWordChars}]+|\\s+|[^${extendedWordChars}]`, "ug");
  var WordDiff = class extends Diff {
    equals(left, right, options) {
      if (options.ignoreCase) {
        left = left.toLowerCase();
        right = right.toLowerCase();
      }
      return left.trim() === right.trim();
    }
    tokenize(value, options = {}) {
      let parts;
      if (options.intlSegmenter) {
        const segmenter = options.intlSegmenter;
        if (segmenter.resolvedOptions().granularity != "word") {
          throw new Error('The segmenter passed must have a granularity of "word"');
        }
        parts = [];
        for (const segmentObj of Array.from(segmenter.segment(value))) {
          const segment = segmentObj.segment;
          if (parts.length && /\s/.test(parts[parts.length - 1]) && /\s/.test(segment)) {
            parts[parts.length - 1] += segment;
          } else {
            parts.push(segment);
          }
        }
      } else {
        parts = value.match(tokenizeIncludingWhitespace) || [];
      }
      const tokens = [];
      let prevPart = null;
      parts.forEach((part) => {
        if (/\s/.test(part)) {
          if (prevPart == null) {
            tokens.push(part);
          } else {
            tokens.push(tokens.pop() + part);
          }
        } else if (prevPart != null && /\s/.test(prevPart)) {
          if (tokens[tokens.length - 1] == prevPart) {
            tokens.push(tokens.pop() + part);
          } else {
            tokens.push(prevPart + part);
          }
        } else {
          tokens.push(part);
        }
        prevPart = part;
      });
      return tokens;
    }
    join(tokens) {
      return tokens.map((token, i) => {
        if (i == 0) {
          return token;
        } else {
          return token.replace(/^\s+/, "");
        }
      }).join("");
    }
    postProcess(changes, options) {
      if (!changes || options.oneChangePerToken) {
        return changes;
      }
      let lastKeep = null;
      let insertion = null;
      let deletion = null;
      changes.forEach((change) => {
        if (change.added) {
          insertion = change;
        } else if (change.removed) {
          deletion = change;
        } else {
          if (insertion || deletion) {
            dedupeWhitespaceInChangeObjects(lastKeep, deletion, insertion, change);
          }
          lastKeep = change;
          insertion = null;
          deletion = null;
        }
      });
      if (insertion || deletion) {
        dedupeWhitespaceInChangeObjects(lastKeep, deletion, insertion, null);
      }
      return changes;
    }
  };
  var wordDiff = new WordDiff();
  function dedupeWhitespaceInChangeObjects(startKeep, deletion, insertion, endKeep) {
    if (deletion && insertion) {
      const oldWsPrefix = leadingWs(deletion.value);
      const oldWsSuffix = trailingWs(deletion.value);
      const newWsPrefix = leadingWs(insertion.value);
      const newWsSuffix = trailingWs(insertion.value);
      if (startKeep) {
        const commonWsPrefix = longestCommonPrefix(oldWsPrefix, newWsPrefix);
        startKeep.value = replaceSuffix(startKeep.value, newWsPrefix, commonWsPrefix);
        deletion.value = removePrefix(deletion.value, commonWsPrefix);
        insertion.value = removePrefix(insertion.value, commonWsPrefix);
      }
      if (endKeep) {
        const commonWsSuffix = longestCommonSuffix(oldWsSuffix, newWsSuffix);
        endKeep.value = replacePrefix(endKeep.value, newWsSuffix, commonWsSuffix);
        deletion.value = removeSuffix(deletion.value, commonWsSuffix);
        insertion.value = removeSuffix(insertion.value, commonWsSuffix);
      }
    } else if (insertion) {
      if (startKeep) {
        const ws = leadingWs(insertion.value);
        insertion.value = insertion.value.substring(ws.length);
      }
      if (endKeep) {
        const ws = leadingWs(endKeep.value);
        endKeep.value = endKeep.value.substring(ws.length);
      }
    } else if (startKeep && endKeep) {
      const newWsFull = leadingWs(endKeep.value), delWsStart = leadingWs(deletion.value), delWsEnd = trailingWs(deletion.value);
      const newWsStart = longestCommonPrefix(newWsFull, delWsStart);
      deletion.value = removePrefix(deletion.value, newWsStart);
      const newWsEnd = longestCommonSuffix(removePrefix(newWsFull, newWsStart), delWsEnd);
      deletion.value = removeSuffix(deletion.value, newWsEnd);
      endKeep.value = replacePrefix(endKeep.value, newWsFull, newWsEnd);
      startKeep.value = replaceSuffix(startKeep.value, newWsFull, newWsFull.slice(0, newWsFull.length - newWsEnd.length));
    } else if (endKeep) {
      const endKeepWsPrefix = leadingWs(endKeep.value);
      const deletionWsSuffix = trailingWs(deletion.value);
      const overlap = maximumOverlap(deletionWsSuffix, endKeepWsPrefix);
      deletion.value = removeSuffix(deletion.value, overlap);
    } else if (startKeep) {
      const startKeepWsSuffix = trailingWs(startKeep.value);
      const deletionWsPrefix = leadingWs(deletion.value);
      const overlap = maximumOverlap(startKeepWsSuffix, deletionWsPrefix);
      deletion.value = removePrefix(deletion.value, overlap);
    }
  }
  var WordsWithSpaceDiff = class extends Diff {
    tokenize(value) {
      const regex2 = new RegExp(`(\\r?\\n)|[${extendedWordChars}]+|[^\\S\\n\\r]+|[^${extendedWordChars}]`, "ug");
      return value.match(regex2) || [];
    }
  };
  var wordsWithSpaceDiff = new WordsWithSpaceDiff();
  function diffWordsWithSpace(oldStr, newStr, options) {
    return wordsWithSpaceDiff.diff(oldStr, newStr, options);
  }

  // node_modules/diff2html/lib-esm/rematch.js
  function levenshtein(a, b) {
    if (a.length === 0) {
      return b.length;
    }
    if (b.length === 0) {
      return a.length;
    }
    const matrix = [];
    let i;
    for (i = 0; i <= b.length; i++) {
      matrix[i] = [i];
    }
    let j;
    for (j = 0; j <= a.length; j++) {
      matrix[0][j] = j;
    }
    for (i = 1; i <= b.length; i++) {
      for (j = 1; j <= a.length; j++) {
        if (b.charAt(i - 1) === a.charAt(j - 1)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(matrix[i - 1][j - 1] + 1, Math.min(matrix[i][j - 1] + 1, matrix[i - 1][j] + 1));
        }
      }
    }
    return matrix[b.length][a.length];
  }
  function newDistanceFn(str) {
    return (x, y) => {
      const xValue = str(x).trim();
      const yValue = str(y).trim();
      const lev = levenshtein(xValue, yValue);
      return lev / (xValue.length + yValue.length);
    };
  }
  function newMatcherFn(distance2) {
    function findBestMatch(a, b, cache = /* @__PURE__ */ new Map()) {
      let bestMatchDist = Infinity;
      let bestMatch;
      for (let i = 0; i < a.length; ++i) {
        for (let j = 0; j < b.length; ++j) {
          const cacheKey = JSON.stringify([a[i], b[j]]);
          let md;
          if (!(cache.has(cacheKey) && (md = cache.get(cacheKey)))) {
            md = distance2(a[i], b[j]);
            cache.set(cacheKey, md);
          }
          if (md < bestMatchDist) {
            bestMatchDist = md;
            bestMatch = { indexA: i, indexB: j, score: bestMatchDist };
          }
        }
      }
      return bestMatch;
    }
    function group(a, b, level = 0, cache = /* @__PURE__ */ new Map()) {
      const bm = findBestMatch(a, b, cache);
      if (!bm || a.length + b.length < 3) {
        return [[a, b]];
      }
      const a1 = a.slice(0, bm.indexA);
      const b1 = b.slice(0, bm.indexB);
      const aMatch = [a[bm.indexA]];
      const bMatch = [b[bm.indexB]];
      const tailA = bm.indexA + 1;
      const tailB = bm.indexB + 1;
      const a2 = a.slice(tailA);
      const b2 = b.slice(tailB);
      const group1 = group(a1, b1, level + 1, cache);
      const groupMatch = group(aMatch, bMatch, level + 1, cache);
      const group2 = group(a2, b2, level + 1, cache);
      let result = groupMatch;
      if (bm.indexA > 0 || bm.indexB > 0) {
        result = group1.concat(result);
      }
      if (a.length > tailA || b.length > tailB) {
        result = result.concat(group2);
      }
      return result;
    }
    return group;
  }

  // node_modules/diff2html/lib-esm/render-utils.js
  var CSSLineClass = {
    INSERTS: "d2h-ins",
    DELETES: "d2h-del",
    CONTEXT: "d2h-cntx",
    INFO: "d2h-info",
    INSERT_CHANGES: "d2h-ins d2h-change",
    DELETE_CHANGES: "d2h-del d2h-change"
  };
  var defaultRenderConfig = {
    matching: LineMatchingType.NONE,
    matchWordsThreshold: 0.25,
    maxLineLengthHighlight: 1e4,
    diffStyle: DiffStyleType.WORD,
    colorScheme: ColorSchemeType.LIGHT
  };
  var separator = "/";
  var distance = newDistanceFn((change) => change.value);
  var matcher = newMatcherFn(distance);
  function isDevNullName(name) {
    return name.indexOf("dev/null") !== -1;
  }
  function removeInsElements(line) {
    return line.replace(/(<ins[^>]*>((.|\n)*?)<\/ins>)/g, "");
  }
  function removeDelElements(line) {
    return line.replace(/(<del[^>]*>((.|\n)*?)<\/del>)/g, "");
  }
  function toCSSClass(lineType) {
    switch (lineType) {
      case LineType.CONTEXT:
        return CSSLineClass.CONTEXT;
      case LineType.INSERT:
        return CSSLineClass.INSERTS;
      case LineType.DELETE:
        return CSSLineClass.DELETES;
    }
  }
  function colorSchemeToCss(colorScheme) {
    switch (colorScheme) {
      case ColorSchemeType.DARK:
        return "d2h-dark-color-scheme";
      case ColorSchemeType.AUTO:
        return "d2h-auto-color-scheme";
      case ColorSchemeType.LIGHT:
      default:
        return "d2h-light-color-scheme";
    }
  }
  function prefixLength(isCombined) {
    return isCombined ? 2 : 1;
  }
  function escapeForHtml(str) {
    return str.slice(0).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;").replace(/\//g, "&#x2F;");
  }
  function deconstructLine(line, isCombined, escape = true) {
    const indexToSplit = prefixLength(isCombined);
    return {
      prefix: line.substring(0, indexToSplit),
      content: escape ? escapeForHtml(line.substring(indexToSplit)) : line.substring(indexToSplit)
    };
  }
  function filenameDiff(file) {
    const oldFilename = unifyPath(file.oldName);
    const newFilename = unifyPath(file.newName);
    if (oldFilename !== newFilename && !isDevNullName(oldFilename) && !isDevNullName(newFilename)) {
      const prefixPaths = [];
      const suffixPaths = [];
      const oldFilenameParts = oldFilename.split(separator);
      const newFilenameParts = newFilename.split(separator);
      const oldFilenamePartsSize = oldFilenameParts.length;
      const newFilenamePartsSize = newFilenameParts.length;
      let i = 0;
      let j = oldFilenamePartsSize - 1;
      let k = newFilenamePartsSize - 1;
      while (i < j && i < k) {
        if (oldFilenameParts[i] === newFilenameParts[i]) {
          prefixPaths.push(newFilenameParts[i]);
          i += 1;
        } else {
          break;
        }
      }
      while (j > i && k > i) {
        if (oldFilenameParts[j] === newFilenameParts[k]) {
          suffixPaths.unshift(newFilenameParts[k]);
          j -= 1;
          k -= 1;
        } else {
          break;
        }
      }
      const finalPrefix = prefixPaths.join(separator);
      const finalSuffix = suffixPaths.join(separator);
      const oldRemainingPath = oldFilenameParts.slice(i, j + 1).join(separator);
      const newRemainingPath = newFilenameParts.slice(i, k + 1).join(separator);
      if (finalPrefix.length && finalSuffix.length) {
        return finalPrefix + separator + "{" + oldRemainingPath + " \u2192 " + newRemainingPath + "}" + separator + finalSuffix;
      } else if (finalPrefix.length) {
        return finalPrefix + separator + "{" + oldRemainingPath + " \u2192 " + newRemainingPath + "}";
      } else if (finalSuffix.length) {
        return "{" + oldRemainingPath + " \u2192 " + newRemainingPath + "}" + separator + finalSuffix;
      }
      return oldFilename + " \u2192 " + newFilename;
    } else if (!isDevNullName(newFilename)) {
      return newFilename;
    } else {
      return oldFilename;
    }
  }
  function getHtmlId(file) {
    return `d2h-${hashCode(filenameDiff(file)).toString().slice(-6)}`;
  }
  function getFileIcon(file) {
    let templateName = "file-changed";
    if (file.isRename) {
      templateName = "file-renamed";
    } else if (file.isCopy) {
      templateName = "file-renamed";
    } else if (file.isNew) {
      templateName = "file-added";
    } else if (file.isDeleted) {
      templateName = "file-deleted";
    } else if (file.newName !== file.oldName) {
      templateName = "file-renamed";
    }
    return templateName;
  }
  function diffHighlight(diffLine1, diffLine2, isCombined, config = {}) {
    const { matching, maxLineLengthHighlight, matchWordsThreshold, diffStyle } = Object.assign(Object.assign({}, defaultRenderConfig), config);
    const line1 = deconstructLine(diffLine1, isCombined, false);
    const line2 = deconstructLine(diffLine2, isCombined, false);
    if (line1.content.length > maxLineLengthHighlight || line2.content.length > maxLineLengthHighlight) {
      return {
        oldLine: {
          prefix: line1.prefix,
          content: escapeForHtml(line1.content)
        },
        newLine: {
          prefix: line2.prefix,
          content: escapeForHtml(line2.content)
        }
      };
    }
    const diff = diffStyle === "char" ? diffChars(line1.content, line2.content) : diffWordsWithSpace(line1.content, line2.content);
    const changedWords = [];
    if (diffStyle === "word" && matching === "words") {
      const removed = diff.filter((element) => element.removed);
      const added = diff.filter((element) => element.added);
      const chunks = matcher(added, removed);
      chunks.forEach((chunk) => {
        if (chunk[0].length === 1 && chunk[1].length === 1) {
          const dist = distance(chunk[0][0], chunk[1][0]);
          if (dist < matchWordsThreshold) {
            changedWords.push(chunk[0][0]);
            changedWords.push(chunk[1][0]);
          }
        }
      });
    }
    const highlightedLine = diff.reduce((highlightedLine2, part) => {
      const elemType = part.added ? "ins" : part.removed ? "del" : null;
      const addClass = changedWords.indexOf(part) > -1 ? ' class="d2h-change"' : "";
      const escapedValue = escapeForHtml(part.value);
      return elemType !== null ? `${highlightedLine2}<${elemType}${addClass}>${escapedValue}</${elemType}>` : `${highlightedLine2}${escapedValue}`;
    }, "");
    return {
      oldLine: {
        prefix: line1.prefix,
        content: removeInsElements(highlightedLine)
      },
      newLine: {
        prefix: line2.prefix,
        content: removeDelElements(highlightedLine)
      }
    };
  }

  // node_modules/diff2html/lib-esm/file-list-renderer.js
  var baseTemplatesPath = "file-summary";
  var iconsBaseTemplatesPath = "icon";
  var defaultFileListRendererConfig = {
    colorScheme: defaultRenderConfig.colorScheme
  };
  var FileListRenderer = class {
    constructor(hoganUtils, config = {}) {
      this.hoganUtils = hoganUtils;
      this.config = Object.assign(Object.assign({}, defaultFileListRendererConfig), config);
    }
    render(diffFiles) {
      const files = diffFiles.map((file) => this.hoganUtils.render(baseTemplatesPath, "line", {
        fileHtmlId: getHtmlId(file),
        oldName: file.oldName,
        newName: file.newName,
        fileName: filenameDiff(file),
        deletedLines: "-" + file.deletedLines,
        addedLines: "+" + file.addedLines
      }, {
        fileIcon: this.hoganUtils.template(iconsBaseTemplatesPath, getFileIcon(file))
      })).join("\n");
      return this.hoganUtils.render(baseTemplatesPath, "wrapper", {
        colorScheme: colorSchemeToCss(this.config.colorScheme),
        filesNumber: diffFiles.length,
        files
      });
    }
  };

  // node_modules/diff2html/lib-esm/line-by-line-renderer.js
  var defaultLineByLineRendererConfig = Object.assign(Object.assign({}, defaultRenderConfig), { renderNothingWhenEmpty: false, matchingMaxComparisons: 2500, maxLineSizeInBlockForComparison: 200 });
  var genericTemplatesPath = "generic";
  var baseTemplatesPath2 = "line-by-line";
  var iconsBaseTemplatesPath2 = "icon";
  var tagsBaseTemplatesPath = "tag";
  var LineByLineRenderer = class {
    constructor(hoganUtils, config = {}) {
      this.hoganUtils = hoganUtils;
      this.config = Object.assign(Object.assign({}, defaultLineByLineRendererConfig), config);
    }
    render(diffFiles) {
      const diffsHtml = diffFiles.map((file) => {
        let diffs;
        if (file.blocks.length) {
          diffs = this.generateFileHtml(file);
        } else {
          diffs = this.generateEmptyDiff();
        }
        return this.makeFileDiffHtml(file, diffs);
      }).join("\n");
      return this.hoganUtils.render(genericTemplatesPath, "wrapper", {
        colorScheme: colorSchemeToCss(this.config.colorScheme),
        content: diffsHtml
      });
    }
    makeFileDiffHtml(file, diffs) {
      if (this.config.renderNothingWhenEmpty && Array.isArray(file.blocks) && file.blocks.length === 0)
        return "";
      const fileDiffTemplate = this.hoganUtils.template(baseTemplatesPath2, "file-diff");
      const filePathTemplate = this.hoganUtils.template(genericTemplatesPath, "file-path");
      const fileIconTemplate = this.hoganUtils.template(iconsBaseTemplatesPath2, "file");
      const fileTagTemplate = this.hoganUtils.template(tagsBaseTemplatesPath, getFileIcon(file));
      return fileDiffTemplate.render({
        file,
        fileHtmlId: getHtmlId(file),
        diffs,
        filePath: filePathTemplate.render({
          fileDiffName: filenameDiff(file)
        }, {
          fileIcon: fileIconTemplate,
          fileTag: fileTagTemplate
        })
      });
    }
    generateEmptyDiff() {
      return this.hoganUtils.render(genericTemplatesPath, "empty-diff", {
        contentClass: "d2h-code-line",
        CSSLineClass
      });
    }
    generateFileHtml(file) {
      const matcher2 = newMatcherFn(newDistanceFn((e) => deconstructLine(e.content, file.isCombined).content));
      return file.blocks.map((block) => {
        let lines = this.hoganUtils.render(genericTemplatesPath, "block-header", {
          CSSLineClass,
          blockHeader: file.isTooBig ? block.header : escapeForHtml(block.header),
          lineClass: "d2h-code-linenumber",
          contentClass: "d2h-code-line"
        });
        this.applyLineGroupping(block).forEach(([contextLines, oldLines, newLines]) => {
          if (oldLines.length && newLines.length && !contextLines.length) {
            this.applyRematchMatching(oldLines, newLines, matcher2).map(([oldLines2, newLines2]) => {
              const { left, right } = this.processChangedLines(file, file.isCombined, oldLines2, newLines2);
              lines += left;
              lines += right;
            });
          } else if (contextLines.length) {
            contextLines.forEach((line) => {
              const { prefix, content } = deconstructLine(line.content, file.isCombined);
              lines += this.generateSingleLineHtml(file, {
                type: CSSLineClass.CONTEXT,
                prefix,
                content,
                oldNumber: line.oldNumber,
                newNumber: line.newNumber
              });
            });
          } else if (oldLines.length || newLines.length) {
            const { left, right } = this.processChangedLines(file, file.isCombined, oldLines, newLines);
            lines += left;
            lines += right;
          } else {
            console.error("Unknown state reached while processing groups of lines", contextLines, oldLines, newLines);
          }
        });
        return lines;
      }).join("\n");
    }
    applyLineGroupping(block) {
      const blockLinesGroups = [];
      let oldLines = [];
      let newLines = [];
      for (let i = 0; i < block.lines.length; i++) {
        const diffLine = block.lines[i];
        if (diffLine.type !== LineType.INSERT && newLines.length || diffLine.type === LineType.CONTEXT && oldLines.length > 0) {
          blockLinesGroups.push([[], oldLines, newLines]);
          oldLines = [];
          newLines = [];
        }
        if (diffLine.type === LineType.CONTEXT) {
          blockLinesGroups.push([[diffLine], [], []]);
        } else if (diffLine.type === LineType.INSERT && oldLines.length === 0) {
          blockLinesGroups.push([[], [], [diffLine]]);
        } else if (diffLine.type === LineType.INSERT && oldLines.length > 0) {
          newLines.push(diffLine);
        } else if (diffLine.type === LineType.DELETE) {
          oldLines.push(diffLine);
        }
      }
      if (oldLines.length || newLines.length) {
        blockLinesGroups.push([[], oldLines, newLines]);
        oldLines = [];
        newLines = [];
      }
      return blockLinesGroups;
    }
    applyRematchMatching(oldLines, newLines, matcher2) {
      const comparisons = oldLines.length * newLines.length;
      const maxLineSizeInBlock = max(oldLines.concat(newLines).map((elem) => elem.content.length));
      const doMatching = comparisons < this.config.matchingMaxComparisons && maxLineSizeInBlock < this.config.maxLineSizeInBlockForComparison && (this.config.matching === "lines" || this.config.matching === "words");
      return doMatching ? matcher2(oldLines, newLines) : [[oldLines, newLines]];
    }
    processChangedLines(file, isCombined, oldLines, newLines) {
      const fileHtml = {
        right: "",
        left: ""
      };
      const maxLinesNumber = Math.max(oldLines.length, newLines.length);
      for (let i = 0; i < maxLinesNumber; i++) {
        const oldLine = oldLines[i];
        const newLine = newLines[i];
        const diff = oldLine !== void 0 && newLine !== void 0 ? diffHighlight(oldLine.content, newLine.content, isCombined, this.config) : void 0;
        const preparedOldLine = oldLine !== void 0 && oldLine.oldNumber !== void 0 ? Object.assign(Object.assign({}, diff !== void 0 ? {
          prefix: diff.oldLine.prefix,
          content: diff.oldLine.content,
          type: CSSLineClass.DELETE_CHANGES
        } : Object.assign(Object.assign({}, deconstructLine(oldLine.content, isCombined)), { type: toCSSClass(oldLine.type) })), { oldNumber: oldLine.oldNumber, newNumber: oldLine.newNumber }) : void 0;
        const preparedNewLine = newLine !== void 0 && newLine.newNumber !== void 0 ? Object.assign(Object.assign({}, diff !== void 0 ? {
          prefix: diff.newLine.prefix,
          content: diff.newLine.content,
          type: CSSLineClass.INSERT_CHANGES
        } : Object.assign(Object.assign({}, deconstructLine(newLine.content, isCombined)), { type: toCSSClass(newLine.type) })), { oldNumber: newLine.oldNumber, newNumber: newLine.newNumber }) : void 0;
        const { left, right } = this.generateLineHtml(file, preparedOldLine, preparedNewLine);
        fileHtml.left += left;
        fileHtml.right += right;
      }
      return fileHtml;
    }
    generateLineHtml(file, oldLine, newLine) {
      return {
        left: this.generateSingleLineHtml(file, oldLine),
        right: this.generateSingleLineHtml(file, newLine)
      };
    }
    generateSingleLineHtml(file, line) {
      if (line === void 0)
        return "";
      const lineNumberHtml = this.hoganUtils.render(baseTemplatesPath2, "numbers", {
        oldNumber: line.oldNumber || "",
        newNumber: line.newNumber || ""
      });
      return this.hoganUtils.render(genericTemplatesPath, "line", {
        type: line.type,
        lineClass: "d2h-code-linenumber",
        contentClass: "d2h-code-line",
        prefix: line.prefix === " " ? "&nbsp;" : line.prefix,
        content: line.content,
        lineNumber: lineNumberHtml,
        line,
        file
      });
    }
  };

  // node_modules/diff2html/lib-esm/side-by-side-renderer.js
  var defaultSideBySideRendererConfig = Object.assign(Object.assign({}, defaultRenderConfig), { renderNothingWhenEmpty: false, matchingMaxComparisons: 2500, maxLineSizeInBlockForComparison: 200 });
  var genericTemplatesPath2 = "generic";
  var baseTemplatesPath3 = "side-by-side";
  var iconsBaseTemplatesPath3 = "icon";
  var tagsBaseTemplatesPath2 = "tag";
  var SideBySideRenderer = class {
    constructor(hoganUtils, config = {}) {
      this.hoganUtils = hoganUtils;
      this.config = Object.assign(Object.assign({}, defaultSideBySideRendererConfig), config);
    }
    render(diffFiles) {
      const diffsHtml = diffFiles.map((file) => {
        let diffs;
        if (file.blocks.length) {
          diffs = this.generateFileHtml(file);
        } else {
          diffs = this.generateEmptyDiff();
        }
        return this.makeFileDiffHtml(file, diffs);
      }).join("\n");
      return this.hoganUtils.render(genericTemplatesPath2, "wrapper", {
        colorScheme: colorSchemeToCss(this.config.colorScheme),
        content: diffsHtml
      });
    }
    makeFileDiffHtml(file, diffs) {
      if (this.config.renderNothingWhenEmpty && Array.isArray(file.blocks) && file.blocks.length === 0)
        return "";
      const fileDiffTemplate = this.hoganUtils.template(baseTemplatesPath3, "file-diff");
      const filePathTemplate = this.hoganUtils.template(genericTemplatesPath2, "file-path");
      const fileIconTemplate = this.hoganUtils.template(iconsBaseTemplatesPath3, "file");
      const fileTagTemplate = this.hoganUtils.template(tagsBaseTemplatesPath2, getFileIcon(file));
      return fileDiffTemplate.render({
        file,
        fileHtmlId: getHtmlId(file),
        diffs,
        filePath: filePathTemplate.render({
          fileDiffName: filenameDiff(file)
        }, {
          fileIcon: fileIconTemplate,
          fileTag: fileTagTemplate
        })
      });
    }
    generateEmptyDiff() {
      return {
        right: "",
        left: this.hoganUtils.render(genericTemplatesPath2, "empty-diff", {
          contentClass: "d2h-code-side-line",
          CSSLineClass
        })
      };
    }
    generateFileHtml(file) {
      const matcher2 = newMatcherFn(newDistanceFn((e) => deconstructLine(e.content, file.isCombined).content));
      return file.blocks.map((block) => {
        const fileHtml = {
          left: this.makeHeaderHtml(block.header, file),
          right: this.makeHeaderHtml("")
        };
        this.applyLineGroupping(block).forEach(([contextLines, oldLines, newLines]) => {
          if (oldLines.length && newLines.length && !contextLines.length) {
            this.applyRematchMatching(oldLines, newLines, matcher2).map(([oldLines2, newLines2]) => {
              const { left, right } = this.processChangedLines(file.isCombined, oldLines2, newLines2);
              fileHtml.left += left;
              fileHtml.right += right;
            });
          } else if (contextLines.length) {
            contextLines.forEach((line) => {
              const { prefix, content } = deconstructLine(line.content, file.isCombined);
              const { left, right } = this.generateLineHtml({
                type: CSSLineClass.CONTEXT,
                prefix,
                content,
                number: line.oldNumber
              }, {
                type: CSSLineClass.CONTEXT,
                prefix,
                content,
                number: line.newNumber
              });
              fileHtml.left += left;
              fileHtml.right += right;
            });
          } else if (oldLines.length || newLines.length) {
            const { left, right } = this.processChangedLines(file.isCombined, oldLines, newLines);
            fileHtml.left += left;
            fileHtml.right += right;
          } else {
            console.error("Unknown state reached while processing groups of lines", contextLines, oldLines, newLines);
          }
        });
        return fileHtml;
      }).reduce((accomulated, html2) => {
        return { left: accomulated.left + html2.left, right: accomulated.right + html2.right };
      }, { left: "", right: "" });
    }
    applyLineGroupping(block) {
      const blockLinesGroups = [];
      let oldLines = [];
      let newLines = [];
      for (let i = 0; i < block.lines.length; i++) {
        const diffLine = block.lines[i];
        if (diffLine.type !== LineType.INSERT && newLines.length || diffLine.type === LineType.CONTEXT && oldLines.length > 0) {
          blockLinesGroups.push([[], oldLines, newLines]);
          oldLines = [];
          newLines = [];
        }
        if (diffLine.type === LineType.CONTEXT) {
          blockLinesGroups.push([[diffLine], [], []]);
        } else if (diffLine.type === LineType.INSERT && oldLines.length === 0) {
          blockLinesGroups.push([[], [], [diffLine]]);
        } else if (diffLine.type === LineType.INSERT && oldLines.length > 0) {
          newLines.push(diffLine);
        } else if (diffLine.type === LineType.DELETE) {
          oldLines.push(diffLine);
        }
      }
      if (oldLines.length || newLines.length) {
        blockLinesGroups.push([[], oldLines, newLines]);
        oldLines = [];
        newLines = [];
      }
      return blockLinesGroups;
    }
    applyRematchMatching(oldLines, newLines, matcher2) {
      const comparisons = oldLines.length * newLines.length;
      const maxLineSizeInBlock = max(oldLines.concat(newLines).map((elem) => elem.content.length));
      const doMatching = comparisons < this.config.matchingMaxComparisons && maxLineSizeInBlock < this.config.maxLineSizeInBlockForComparison && (this.config.matching === "lines" || this.config.matching === "words");
      return doMatching ? matcher2(oldLines, newLines) : [[oldLines, newLines]];
    }
    makeHeaderHtml(blockHeader, file) {
      return this.hoganUtils.render(genericTemplatesPath2, "block-header", {
        CSSLineClass,
        blockHeader: (file === null || file === void 0 ? void 0 : file.isTooBig) ? blockHeader : escapeForHtml(blockHeader),
        lineClass: "d2h-code-side-linenumber",
        contentClass: "d2h-code-side-line"
      });
    }
    processChangedLines(isCombined, oldLines, newLines) {
      const fileHtml = {
        right: "",
        left: ""
      };
      const maxLinesNumber = Math.max(oldLines.length, newLines.length);
      for (let i = 0; i < maxLinesNumber; i++) {
        const oldLine = oldLines[i];
        const newLine = newLines[i];
        const diff = oldLine !== void 0 && newLine !== void 0 ? diffHighlight(oldLine.content, newLine.content, isCombined, this.config) : void 0;
        const preparedOldLine = oldLine !== void 0 && oldLine.oldNumber !== void 0 ? Object.assign(Object.assign({}, diff !== void 0 ? {
          prefix: diff.oldLine.prefix,
          content: diff.oldLine.content,
          type: CSSLineClass.DELETE_CHANGES
        } : Object.assign(Object.assign({}, deconstructLine(oldLine.content, isCombined)), { type: toCSSClass(oldLine.type) })), { number: oldLine.oldNumber }) : void 0;
        const preparedNewLine = newLine !== void 0 && newLine.newNumber !== void 0 ? Object.assign(Object.assign({}, diff !== void 0 ? {
          prefix: diff.newLine.prefix,
          content: diff.newLine.content,
          type: CSSLineClass.INSERT_CHANGES
        } : Object.assign(Object.assign({}, deconstructLine(newLine.content, isCombined)), { type: toCSSClass(newLine.type) })), { number: newLine.newNumber }) : void 0;
        const { left, right } = this.generateLineHtml(preparedOldLine, preparedNewLine);
        fileHtml.left += left;
        fileHtml.right += right;
      }
      return fileHtml;
    }
    generateLineHtml(oldLine, newLine) {
      return {
        left: this.generateSingleHtml(oldLine),
        right: this.generateSingleHtml(newLine)
      };
    }
    generateSingleHtml(line) {
      const lineClass = "d2h-code-side-linenumber";
      const contentClass = "d2h-code-side-line";
      return this.hoganUtils.render(genericTemplatesPath2, "line", {
        type: (line === null || line === void 0 ? void 0 : line.type) || `${CSSLineClass.CONTEXT} d2h-emptyplaceholder`,
        lineClass: line !== void 0 ? lineClass : `${lineClass} d2h-code-side-emptyplaceholder`,
        contentClass: line !== void 0 ? contentClass : `${contentClass} d2h-code-side-emptyplaceholder`,
        prefix: (line === null || line === void 0 ? void 0 : line.prefix) === " " ? "&nbsp;" : line === null || line === void 0 ? void 0 : line.prefix,
        content: line === null || line === void 0 ? void 0 : line.content,
        lineNumber: line === null || line === void 0 ? void 0 : line.number
      });
    }
  };

  // node_modules/diff2html/lib-esm/hoganjs-utils.js
  var Hogan3 = __toESM(require_hogan());

  // node_modules/diff2html/lib-esm/diff2html-templates.js
  var Hogan2 = __toESM(require_hogan());
  var defaultTemplates = {};
  defaultTemplates["file-summary-line"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<li class="d2h-file-list-line">');
    t.b("\n" + i);
    t.b('    <span class="d2h-file-name-wrapper">');
    t.b("\n" + i);
    t.b(t.rp("<fileIcon0", c, p, "      "));
    t.b('      <a href="#');
    t.b(t.v(t.f("fileHtmlId", c, p, 0)));
    t.b('" class="d2h-file-name">');
    t.b(t.v(t.f("fileName", c, p, 0)));
    t.b("</a>");
    t.b("\n" + i);
    t.b('      <span class="d2h-file-stats">');
    t.b("\n" + i);
    t.b('          <span class="d2h-lines-added">');
    t.b(t.v(t.f("addedLines", c, p, 0)));
    t.b("</span>");
    t.b("\n" + i);
    t.b('          <span class="d2h-lines-deleted">');
    t.b(t.v(t.f("deletedLines", c, p, 0)));
    t.b("</span>");
    t.b("\n" + i);
    t.b("      </span>");
    t.b("\n" + i);
    t.b("    </span>");
    t.b("\n" + i);
    t.b("</li>");
    return t.fl();
  }, partials: { "<fileIcon0": { name: "fileIcon", partials: {}, subs: {} } }, subs: {} });
  defaultTemplates["file-summary-wrapper"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<div class="d2h-file-list-wrapper ');
    t.b(t.v(t.f("colorScheme", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b('    <div class="d2h-file-list-header">');
    t.b("\n" + i);
    t.b('        <span class="d2h-file-list-title">Files changed (');
    t.b(t.v(t.f("filesNumber", c, p, 0)));
    t.b(")</span>");
    t.b("\n" + i);
    t.b('        <a class="d2h-file-switch d2h-hide">hide</a>');
    t.b("\n" + i);
    t.b('        <a class="d2h-file-switch d2h-show">show</a>');
    t.b("\n" + i);
    t.b("    </div>");
    t.b("\n" + i);
    t.b('    <ol class="d2h-file-list">');
    t.b("\n" + i);
    t.b("    ");
    t.b(t.t(t.f("files", c, p, 0)));
    t.b("\n" + i);
    t.b("    </ol>");
    t.b("\n" + i);
    t.b("</div>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["generic-block-header"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b("<tr>");
    t.b("\n" + i);
    t.b('    <td class="');
    t.b(t.v(t.f("lineClass", c, p, 0)));
    t.b(" ");
    t.b(t.v(t.d("CSSLineClass.INFO", c, p, 0)));
    t.b('"></td>');
    t.b("\n" + i);
    t.b('    <td class="');
    t.b(t.v(t.d("CSSLineClass.INFO", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b('        <div class="');
    t.b(t.v(t.f("contentClass", c, p, 0)));
    t.b('">');
    if (t.s(t.f("blockHeader", c, p, 1), c, p, 0, 156, 173, "{{ }}")) {
      t.rs(c, p, function(c2, p2, t2) {
        t2.b(t2.t(t2.f("blockHeader", c2, p2, 0)));
      });
      c.pop();
    }
    if (!t.s(t.f("blockHeader", c, p, 1), c, p, 1, 0, 0, "")) {
      t.b("&nbsp;");
    }
    ;
    t.b("</div>");
    t.b("\n" + i);
    t.b("    </td>");
    t.b("\n" + i);
    t.b("</tr>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["generic-empty-diff"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b("<tr>");
    t.b("\n" + i);
    t.b('    <td class="');
    t.b(t.v(t.d("CSSLineClass.INFO", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b('        <div class="');
    t.b(t.v(t.f("contentClass", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b("            File without changes");
    t.b("\n" + i);
    t.b("        </div>");
    t.b("\n" + i);
    t.b("    </td>");
    t.b("\n" + i);
    t.b("</tr>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["generic-file-path"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<span class="d2h-file-name-wrapper">');
    t.b("\n" + i);
    t.b(t.rp("<fileIcon0", c, p, "    "));
    t.b('    <span class="d2h-file-name">');
    t.b(t.v(t.f("fileDiffName", c, p, 0)));
    t.b("</span>");
    t.b("\n" + i);
    t.b(t.rp("<fileTag1", c, p, "    "));
    t.b("</span>");
    t.b("\n" + i);
    t.b('<label class="d2h-file-collapse">');
    t.b("\n" + i);
    t.b('    <input class="d2h-file-collapse-input" type="checkbox" name="viewed" value="viewed">');
    t.b("\n" + i);
    t.b("    Viewed");
    t.b("\n" + i);
    t.b("</label>");
    return t.fl();
  }, partials: { "<fileIcon0": { name: "fileIcon", partials: {}, subs: {} }, "<fileTag1": { name: "fileTag", partials: {}, subs: {} } }, subs: {} });
  defaultTemplates["generic-line"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b("<tr>");
    t.b("\n" + i);
    t.b('    <td class="');
    t.b(t.v(t.f("lineClass", c, p, 0)));
    t.b(" ");
    t.b(t.v(t.f("type", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b("      ");
    t.b(t.t(t.f("lineNumber", c, p, 0)));
    t.b("\n" + i);
    t.b("    </td>");
    t.b("\n" + i);
    t.b('    <td class="');
    t.b(t.v(t.f("type", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b('        <div class="');
    t.b(t.v(t.f("contentClass", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    if (t.s(t.f("prefix", c, p, 1), c, p, 0, 162, 238, "{{ }}")) {
      t.rs(c, p, function(c2, p2, t2) {
        t2.b('            <span class="d2h-code-line-prefix">');
        t2.b(t2.t(t2.f("prefix", c2, p2, 0)));
        t2.b("</span>");
        t2.b("\n" + i);
      });
      c.pop();
    }
    if (!t.s(t.f("prefix", c, p, 1), c, p, 1, 0, 0, "")) {
      t.b('            <span class="d2h-code-line-prefix">&nbsp;</span>');
      t.b("\n" + i);
    }
    ;
    if (t.s(t.f("content", c, p, 1), c, p, 0, 371, 445, "{{ }}")) {
      t.rs(c, p, function(c2, p2, t2) {
        t2.b('            <span class="d2h-code-line-ctn">');
        t2.b(t2.t(t2.f("content", c2, p2, 0)));
        t2.b("</span>");
        t2.b("\n" + i);
      });
      c.pop();
    }
    if (!t.s(t.f("content", c, p, 1), c, p, 1, 0, 0, "")) {
      t.b('            <span class="d2h-code-line-ctn"><br></span>');
      t.b("\n" + i);
    }
    ;
    t.b("        </div>");
    t.b("\n" + i);
    t.b("    </td>");
    t.b("\n" + i);
    t.b("</tr>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["generic-wrapper"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<div class="d2h-wrapper ');
    t.b(t.v(t.f("colorScheme", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b("    ");
    t.b(t.t(t.f("content", c, p, 0)));
    t.b("\n" + i);
    t.b("</div>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["icon-file-added"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<svg aria-hidden="true" class="d2h-icon d2h-added" height="16" title="added" version="1.1" viewBox="0 0 14 16"');
    t.b("\n" + i);
    t.b('     width="14">');
    t.b("\n" + i);
    t.b('    <path d="M13 1H1C0.45 1 0 1.45 0 2v12c0 0.55 0.45 1 1 1h12c0.55 0 1-0.45 1-1V2c0-0.55-0.45-1-1-1z m0 13H1V2h12v12zM6 9H3V7h3V4h2v3h3v2H8v3H6V9z"></path>');
    t.b("\n" + i);
    t.b("</svg>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["icon-file-changed"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<svg aria-hidden="true" class="d2h-icon d2h-changed" height="16" title="modified" version="1.1"');
    t.b("\n" + i);
    t.b('     viewBox="0 0 14 16" width="14">');
    t.b("\n" + i);
    t.b('    <path d="M13 1H1C0.45 1 0 1.45 0 2v12c0 0.55 0.45 1 1 1h12c0.55 0 1-0.45 1-1V2c0-0.55-0.45-1-1-1z m0 13H1V2h12v12zM4 8c0-1.66 1.34-3 3-3s3 1.34 3 3-1.34 3-3 3-3-1.34-3-3z"></path>');
    t.b("\n" + i);
    t.b("</svg>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["icon-file-deleted"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<svg aria-hidden="true" class="d2h-icon d2h-deleted" height="16" title="removed" version="1.1"');
    t.b("\n" + i);
    t.b('     viewBox="0 0 14 16" width="14">');
    t.b("\n" + i);
    t.b('    <path d="M13 1H1C0.45 1 0 1.45 0 2v12c0 0.55 0.45 1 1 1h12c0.55 0 1-0.45 1-1V2c0-0.55-0.45-1-1-1z m0 13H1V2h12v12zM11 9H3V7h8v2z"></path>');
    t.b("\n" + i);
    t.b("</svg>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["icon-file-renamed"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<svg aria-hidden="true" class="d2h-icon d2h-moved" height="16" title="renamed" version="1.1"');
    t.b("\n" + i);
    t.b('     viewBox="0 0 14 16" width="14">');
    t.b("\n" + i);
    t.b('    <path d="M6 9H3V7h3V4l5 4-5 4V9z m8-7v12c0 0.55-0.45 1-1 1H1c-0.55 0-1-0.45-1-1V2c0-0.55 0.45-1 1-1h12c0.55 0 1 0.45 1 1z m-1 0H1v12h12V2z"></path>');
    t.b("\n" + i);
    t.b("</svg>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["icon-file"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<svg aria-hidden="true" class="d2h-icon" height="16" version="1.1" viewBox="0 0 12 16" width="12">');
    t.b("\n" + i);
    t.b('    <path d="M6 5H2v-1h4v1zM2 8h7v-1H2v1z m0 2h7v-1H2v1z m0 2h7v-1H2v1z m10-7.5v9.5c0 0.55-0.45 1-1 1H1c-0.55 0-1-0.45-1-1V2c0-0.55 0.45-1 1-1h7.5l3.5 3.5z m-1 0.5L8 2H1v12h10V5z"></path>');
    t.b("\n" + i);
    t.b("</svg>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["line-by-line-file-diff"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<div id="');
    t.b(t.v(t.f("fileHtmlId", c, p, 0)));
    t.b('" class="d2h-file-wrapper" data-lang="');
    t.b(t.v(t.d("file.language", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b('    <div class="d2h-file-header">');
    t.b("\n" + i);
    t.b("    ");
    t.b(t.t(t.f("filePath", c, p, 0)));
    t.b("\n" + i);
    t.b("    </div>");
    t.b("\n" + i);
    t.b('    <div class="d2h-file-diff">');
    t.b("\n" + i);
    t.b('        <div class="d2h-code-wrapper">');
    t.b("\n" + i);
    t.b('            <table class="d2h-diff-table">');
    t.b("\n" + i);
    t.b('                <tbody class="d2h-diff-tbody">');
    t.b("\n" + i);
    t.b("                ");
    t.b(t.t(t.f("diffs", c, p, 0)));
    t.b("\n" + i);
    t.b("                </tbody>");
    t.b("\n" + i);
    t.b("            </table>");
    t.b("\n" + i);
    t.b("        </div>");
    t.b("\n" + i);
    t.b("    </div>");
    t.b("\n" + i);
    t.b("</div>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["line-by-line-numbers"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<div class="line-num1">');
    t.b(t.v(t.f("oldNumber", c, p, 0)));
    t.b("</div>");
    t.b("\n" + i);
    t.b('<div class="line-num2">');
    t.b(t.v(t.f("newNumber", c, p, 0)));
    t.b("</div>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["side-by-side-file-diff"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<div id="');
    t.b(t.v(t.f("fileHtmlId", c, p, 0)));
    t.b('" class="d2h-file-wrapper" data-lang="');
    t.b(t.v(t.d("file.language", c, p, 0)));
    t.b('">');
    t.b("\n" + i);
    t.b('    <div class="d2h-file-header">');
    t.b("\n" + i);
    t.b("      ");
    t.b(t.t(t.f("filePath", c, p, 0)));
    t.b("\n" + i);
    t.b("    </div>");
    t.b("\n" + i);
    t.b('    <div class="d2h-files-diff">');
    t.b("\n" + i);
    t.b('        <div class="d2h-file-side-diff">');
    t.b("\n" + i);
    t.b('            <div class="d2h-code-wrapper">');
    t.b("\n" + i);
    t.b('                <table class="d2h-diff-table">');
    t.b("\n" + i);
    t.b('                    <tbody class="d2h-diff-tbody">');
    t.b("\n" + i);
    t.b("                    ");
    t.b(t.t(t.d("diffs.left", c, p, 0)));
    t.b("\n" + i);
    t.b("                    </tbody>");
    t.b("\n" + i);
    t.b("                </table>");
    t.b("\n" + i);
    t.b("            </div>");
    t.b("\n" + i);
    t.b("        </div>");
    t.b("\n" + i);
    t.b('        <div class="d2h-file-side-diff">');
    t.b("\n" + i);
    t.b('            <div class="d2h-code-wrapper">');
    t.b("\n" + i);
    t.b('                <table class="d2h-diff-table">');
    t.b("\n" + i);
    t.b('                    <tbody class="d2h-diff-tbody">');
    t.b("\n" + i);
    t.b("                    ");
    t.b(t.t(t.d("diffs.right", c, p, 0)));
    t.b("\n" + i);
    t.b("                    </tbody>");
    t.b("\n" + i);
    t.b("                </table>");
    t.b("\n" + i);
    t.b("            </div>");
    t.b("\n" + i);
    t.b("        </div>");
    t.b("\n" + i);
    t.b("    </div>");
    t.b("\n" + i);
    t.b("</div>");
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["tag-file-added"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<span class="d2h-tag d2h-added d2h-added-tag">ADDED</span>');
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["tag-file-changed"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<span class="d2h-tag d2h-changed d2h-changed-tag">CHANGED</span>');
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["tag-file-deleted"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<span class="d2h-tag d2h-deleted d2h-deleted-tag">DELETED</span>');
    return t.fl();
  }, partials: {}, subs: {} });
  defaultTemplates["tag-file-renamed"] = new Hogan2.Template({ code: function(c, p, i) {
    var t = this;
    t.b(i = i || "");
    t.b('<span class="d2h-tag d2h-moved d2h-moved-tag">RENAMED</span>');
    return t.fl();
  }, partials: {}, subs: {} });

  // node_modules/diff2html/lib-esm/hoganjs-utils.js
  var HoganJsUtils = class {
    constructor({ compiledTemplates = {}, rawTemplates = {} }) {
      const compiledRawTemplates = Object.entries(rawTemplates).reduce((previousTemplates, [name, templateString]) => {
        const compiledTemplate = Hogan3.compile(templateString, { asString: false });
        return Object.assign(Object.assign({}, previousTemplates), { [name]: compiledTemplate });
      }, {});
      this.preCompiledTemplates = Object.assign(Object.assign(Object.assign({}, defaultTemplates), compiledTemplates), compiledRawTemplates);
    }
    static compile(templateString) {
      return Hogan3.compile(templateString, { asString: false });
    }
    render(namespace, view, params, partials, indent) {
      const templateKey = this.templateKey(namespace, view);
      try {
        const template = this.preCompiledTemplates[templateKey];
        return template.render(params, partials, indent);
      } catch (_e) {
        throw new Error(`Could not find template to render '${templateKey}'`);
      }
    }
    template(namespace, view) {
      return this.preCompiledTemplates[this.templateKey(namespace, view)];
    }
    templateKey(namespace, view) {
      return `${namespace}-${view}`;
    }
  };

  // node_modules/diff2html/lib-esm/diff2html.js
  var defaultDiff2HtmlConfig = Object.assign(Object.assign(Object.assign({}, defaultLineByLineRendererConfig), defaultSideBySideRendererConfig), { outputFormat: OutputFormatType.LINE_BY_LINE, drawFileList: true });
  function parse2(diffInput, configuration = {}) {
    return parse(diffInput, Object.assign(Object.assign({}, defaultDiff2HtmlConfig), configuration));
  }
  function html(diffInput, configuration = {}) {
    const config = Object.assign(Object.assign({}, defaultDiff2HtmlConfig), configuration);
    const diffJson = typeof diffInput === "string" ? parse(diffInput, config) : diffInput;
    const hoganUtils = new HoganJsUtils(config);
    const { colorScheme } = config;
    const fileListRendererConfig = { colorScheme };
    const fileList = config.drawFileList ? new FileListRenderer(hoganUtils, fileListRendererConfig).render(diffJson) : "";
    const diffOutput = config.outputFormat === "side-by-side" ? new SideBySideRenderer(hoganUtils, config).render(diffJson) : new LineByLineRenderer(hoganUtils, config).render(diffJson);
    return fileList + diffOutput;
  }

  // src/app.js
  var _currentTeam = "";
  var _teams = [];
  var _isMuted = localStorage.getItem("boss-muted") === "true";
  var _audioCtx = null;
  var _lastMsgTimestamp = "";
  var _prevTaskStatuses = {};
  var _msgSendCooldown = false;
  var _expandedTasks = /* @__PURE__ */ new Set();
  var _taskStatsCache = {};
  var _rejectReasonVisible = false;
  var _panelMode = null;
  var _panelAgent = null;
  var _agentTabData = {};
  var _agentCurrentTab = "inbox";
  var _diffRawText = "";
  var _diffCurrentTab = "files";
  var _recognition = null;
  var _micActive = false;
  var _micStopping = false;
  var _micBaseText = "";
  var _micFinalText = "";
  async function loadTeams() {
    try {
      const res = await fetch("/teams");
      if (!res.ok) return;
      _teams = await res.json();
      const sel = document.getElementById("teamSelector");
      const prev = _currentTeam;
      sel.innerHTML = _teams.map((t) => `<option value="${t}">${t}</option>`).join("");
      if (prev && _teams.includes(prev)) {
        sel.value = prev;
      } else if (_teams.length > 0) {
        sel.value = _teams[0];
      }
      _currentTeam = sel.value;
    } catch (e) {
      console.warn("loadTeams failed:", e);
    }
  }
  function onTeamChange() {
    _currentTeam = document.getElementById("teamSelector").value;
    loadChat();
    loadAgents();
    loadSidebar();
  }
  function toggleMute() {
    _isMuted = !_isMuted;
    localStorage.setItem("boss-muted", _isMuted ? "true" : "false");
    _updateMuteBtn();
  }
  function _updateMuteBtn() {
    const btn = document.getElementById("muteToggle");
    if (!btn) return;
    if (_isMuted) {
      btn.innerHTML = "<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><polygon points='2,6 2,10 5,10 9,13 9,3 5,6'/><line x1='12' y1='5' x2='15' y2='11'/><line x1='15' y1='5' x2='12' y2='11'/></svg>";
      btn.title = "Unmute notifications";
    } else {
      btn.innerHTML = "<svg width='16' height='16' viewBox='0 0 16 16' fill='none' stroke='currentColor' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'><polygon points='2,6 2,10 5,10 9,13 9,3 5,6'/><path d='M11.5 5.5a3.5 3.5 0 0 1 0 5'/></svg>";
      btn.title = "Mute notifications";
    }
  }
  function _getAudioCtx() {
    if (!_audioCtx) {
      try {
        _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) {
        return null;
      }
    }
    return _audioCtx;
  }
  function playMsgSound() {
    if (_isMuted) return;
    const ctx = _getAudioCtx();
    if (!ctx) return;
    const now = ctx.currentTime;
    const g = ctx.createGain();
    g.connect(ctx.destination);
    g.gain.setValueAtTime(0.15, now);
    g.gain.exponentialRampToValueAtTime(1e-3, now + 0.25);
    const o1 = ctx.createOscillator();
    o1.type = "sine";
    o1.frequency.value = 800;
    o1.connect(g);
    o1.start(now);
    o1.stop(now + 0.08);
    const o2 = ctx.createOscillator();
    o2.type = "sine";
    o2.frequency.value = 1e3;
    o2.connect(g);
    o2.start(now + 0.1);
    o2.stop(now + 0.18);
  }
  function playTaskSound() {
    if (_isMuted) return;
    const ctx = _getAudioCtx();
    if (!ctx) return;
    const now = ctx.currentTime;
    [523.25, 659.25, 783.99].forEach((freq, i) => {
      const t = now + i * 0.15;
      const g = ctx.createGain();
      g.connect(ctx.destination);
      g.gain.setValueAtTime(0.12, t);
      g.gain.exponentialRampToValueAtTime(1e-3, t + 0.15);
      const o = ctx.createOscillator();
      o.type = "sine";
      o.frequency.value = freq;
      o.connect(g);
      o.start(t);
      o.stop(t + 0.15);
    });
  }
  function cap(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }
  function fmtStatus(s) {
    return s.split("_").map((w) => cap(w)).join(" ");
  }
  function fmtTimestamp(iso) {
    if (!iso) return "\u2014";
    const d = new Date(iso);
    const now = /* @__PURE__ */ new Date();
    const diff = now - d;
    const sec = Math.floor(diff / 1e3);
    const min = Math.floor(sec / 60);
    const hr = Math.floor(min / 60);
    if (sec < 60) return "Just now";
    if (min < 60) return min + " min ago";
    const time = d.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false
    });
    if (hr < 24) return time;
    const mon = d.toLocaleDateString([], { month: "short", day: "numeric" });
    return mon + ", " + time;
  }
  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }
  var _avatarColors = [
    "#e11d48",
    "#7c3aed",
    "#2563eb",
    "#0891b2",
    "#059669",
    "#d97706",
    "#dc2626",
    "#4f46e5"
  ];
  function avatarColor(name) {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = name.charCodeAt(i) + ((h << 5) - h);
    return _avatarColors[Math.abs(h) % _avatarColors.length];
  }
  function avatarInitial(name) {
    return name.charAt(0).toUpperCase();
  }
  function fmtElapsed(sec) {
    if (sec == null) return "\u2014";
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return m > 0 ? m + "m " + s + "s" : s + "s";
  }
  function fmtTokens(tin, tout) {
    if (tin == null && tout == null) return "\u2014";
    return Number(tin || 0).toLocaleString() + " / " + Number(tout || 0).toLocaleString();
  }
  function fmtCost(usd) {
    if (usd == null) return "\u2014";
    return "$" + Number(usd).toFixed(2);
  }
  function switchTab(name, pushHash) {
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.getElementById(name).classList.add("active");
    document.querySelector('.tab[data-tab="' + name + '"]').classList.add("active");
    if (pushHash !== false) window.location.hash = name;
    if (name === "tasks") loadTasks();
    if (name === "chat") loadChat();
    if (name === "agents") loadAgents();
  }
  function _taskRowHtml(t) {
    const expanded = _expandedTasks.has(t.id);
    const s = _taskStatsCache[t.id];
    const tid = "T" + String(t.id).padStart(4, "0");
    return `<div class="task-row${expanded ? " expanded" : ""}" data-id="${t.id}" onclick="toggleTask(${t.id})">
    <div class="task-summary">
      <span class="task-id">${tid}</span>
      <span class="task-title">${esc(t.title)}</span>
      <span><span class="badge badge-${t.status}">${fmtStatus(t.status)}</span></span>
      <span class="task-assignee">${t.assignee ? cap(t.assignee) : "\u2014"}</span>
      <span class="task-priority">${cap(t.priority)}</span>
    </div>
    <div class="task-detail" onclick="event.stopPropagation()">
      <div class="task-detail-grid">
        <div class="task-detail-item"><div class="task-detail-label">Reviewer</div><div class="task-detail-value">${t.reviewer ? cap(t.reviewer) : "\u2014"}</div></div>
        <div class="task-detail-item"><div class="task-detail-label">Time</div><div class="task-detail-value">${s ? fmtElapsed(s.elapsed_seconds) : "\u2014"}</div></div>
        <div class="task-detail-item"><div class="task-detail-label">Tokens (in/out)</div><div class="task-detail-value">${s ? fmtTokens(s.total_tokens_in, s.total_tokens_out) : "\u2014"}</div></div>
        <div class="task-detail-item"><div class="task-detail-label">Cost</div><div class="task-detail-value">${s ? fmtCost(s.total_cost_usd) : "\u2014"}</div></div>
      </div>
      ${s && s.branch ? '<div class="task-vcs-row" onclick="event.stopPropagation()"><span class="task-branch" title="' + esc(s.branch) + '">' + esc(s.branch) + "</span>" + (s.commits && s.commits.length ? s.commits.map(
      (c) => '<button class="task-commit" onclick="event.stopPropagation();openDiffPanel(' + t.id + ')" title="' + esc(String(c)) + '">' + esc(String(c).substring(0, 7)) + "</button>"
    ).join("") : "") + '<button class="btn-diff" onclick="event.stopPropagation();openDiffPanel(' + t.id + ')">View Changes</button></div>' : ""}
      ${t.depends_on && t.depends_on.length ? '<div style="font-size:12px;color:var(--text-muted);margin-bottom:6px">Depends on: ' + t.depends_on.map(
      (d) => '<span class="badge badge-' + (t._dep_statuses && t._dep_statuses[d] || "open") + '" style="font-size:11px;margin-right:4px">T' + String(d).padStart(4, "0") + "</span>"
    ).join("") + "</div>" : ""}
      ${t.base_sha ? '<div style="font-size:11px;color:var(--text-muted);margin-bottom:6px">Base SHA: <code style="font-family:SF Mono,Fira Code,monospace;background:var(--bg-active);padding:2px 6px;border-radius:3px">' + esc(t.base_sha.substring(0, 10)) + "</code></div>" : ""}
      ${t.description ? '<div class="task-desc">' + esc(t.description) + "</div>" : ""}
      <div class="task-dates">
        <span>Created: <span class="ts" data-ts="${t.created_at || ""}">${fmtTimestamp(t.created_at)}</span></span>
        <span>Completed: <span class="ts" data-ts="${t.completed_at || ""}">${fmtTimestamp(t.completed_at)}</span></span>
      </div>
      ${renderTaskApproval(t)}
    </div>
  </div>`;
  }
  function renderTaskApproval(task) {
    const status = task.status || "";
    const approvalStatus = task.approval_status || "";
    if (status === "merged" || approvalStatus === "approved") {
      return '<div class="task-inspector-approval"><div class="approval-badge approval-badge-approved">\u2714 Approved</div></div>';
    }
    if (status === "rejected" || approvalStatus === "rejected") {
      const reason = task.rejection_reason || "";
      return '<div class="task-inspector-approval"><div class="approval-badge approval-badge-rejected">\u2716 Rejected</div>' + (reason ? '<div class="approval-rejection-reason">' + esc(reason) + "</div>" : "") + "</div>";
    }
    if (status === "needs_merge") {
      let html2 = '<div class="task-inspector-approval">';
      html2 += '<div class="task-inspector-approval-actions">';
      html2 += '<button class="btn-approve" onclick="event.stopPropagation();approveTask(' + task.id + ')">Approve Merge</button>';
      html2 += '<button class="btn-reject" onclick="event.stopPropagation();toggleRejectReason(' + task.id + ')">Reject</button>';
      html2 += "</div>";
      if (_rejectReasonVisible) {
        html2 += `<div class="reject-reason-row"><input type="text" class="reject-reason-input" id="rejectReasonInput" placeholder="Reason for rejection..." onclick="event.stopPropagation()" onkeydown="event.stopPropagation();if(event.key==='Enter')rejectTask(` + task.id + ')"><button class="btn-reject" onclick="event.stopPropagation();rejectTask(' + task.id + ')" style="flex-shrink:0">Confirm</button></div>';
      }
      html2 += "</div>";
      return html2;
    }
    if (status === "conflict") {
      return '<div class="task-inspector-approval"><div class="approval-badge" style="background:rgba(251,146,60,0.12);color:#fb923c">\u26A0 Conflict</div></div>';
    }
    return "";
  }
  function toggleRejectReason(taskId) {
    _rejectReasonVisible = !_rejectReasonVisible;
    loadTasks();
    if (_rejectReasonVisible) {
      setTimeout(() => {
        const el = document.getElementById("rejectReasonInput");
        if (el) el.focus();
      }, 50);
    }
  }
  async function approveTask(taskId) {
    try {
      const res = await fetch("/tasks/" + taskId + "/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" }
      });
      if (res.ok) {
        _rejectReasonVisible = false;
        loadTasks();
        loadSidebar();
      } else {
        const err = await res.json().catch(() => ({}));
        alert("Failed to approve: " + (err.detail || res.statusText));
      }
    } catch (e) {
      alert("Failed to approve task: " + e.message);
    }
  }
  async function rejectTask(taskId) {
    const reasonEl = document.getElementById("rejectReasonInput");
    const reason = reasonEl ? reasonEl.value.trim() : "";
    try {
      const res = await fetch("/tasks/" + taskId + "/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: reason || "(no reason)" })
      });
      if (res.ok) {
        _rejectReasonVisible = false;
        loadTasks();
        loadSidebar();
      } else {
        const err = await res.json().catch(() => ({}));
        alert("Failed to reject: " + (err.detail || res.statusText));
      }
    } catch (e) {
      alert("Failed to reject task: " + e.message);
    }
  }
  async function loadTasks() {
    let res;
    try {
      res = await fetch("/tasks");
    } catch (e) {
      console.warn("loadTasks fetch failed:", e);
      return;
    }
    if (!res.ok) return;
    const allTasks = await res.json();
    const el = document.getElementById("taskTable");
    let taskSoundNeeded = false;
    for (const t of allTasks) {
      const prev = _prevTaskStatuses[t.id];
      if (prev && prev !== t.status && (t.status === "done" || t.status === "review"))
        taskSoundNeeded = true;
      _prevTaskStatuses[t.id] = t.status;
    }
    if (taskSoundNeeded) playTaskSound();
    if (!allTasks.length) {
      el.innerHTML = '<p style="color:var(--text-secondary)">No tasks yet.</p>';
      return;
    }
    const assignees = /* @__PURE__ */ new Set();
    for (const t of allTasks) {
      if (t.assignee) assignees.add(t.assignee);
    }
    const assigneeSel = document.getElementById("taskFilterAssignee");
    const prevAssignee = assigneeSel.value;
    assigneeSel.innerHTML = '<option value="">All</option>' + [...assignees].sort().map((n) => `<option value="${n}">${cap(n)}</option>`).join("");
    assigneeSel.value = prevAssignee;
    const filterStatus = document.getElementById("taskFilterStatus").value;
    const filterPriority = document.getElementById("taskFilterPriority").value;
    const filterAssignee = document.getElementById("taskFilterAssignee").value;
    let tasks = allTasks;
    if (filterStatus) tasks = tasks.filter((t) => t.status === filterStatus);
    if (filterPriority)
      tasks = tasks.filter((t) => t.priority === filterPriority);
    if (filterAssignee)
      tasks = tasks.filter((t) => t.assignee === filterAssignee);
    tasks.sort((a, b) => b.id - a.id);
    if (!tasks.length) {
      el.innerHTML = '<p style="color:var(--text-secondary)">No tasks match filters.</p>';
      return;
    }
    await Promise.all(
      tasks.filter((t) => _expandedTasks.has(t.id)).map(async (t) => {
        try {
          const r = await fetch("/tasks/" + t.id + "/stats");
          if (r.ok) _taskStatsCache[t.id] = await r.json();
        } catch (e) {
        }
      })
    );
    el.innerHTML = '<div class="task-list">' + tasks.map((t) => _taskRowHtml(t)).join("") + "</div>";
  }
  function toggleTask(id) {
    if (_expandedTasks.has(id)) _expandedTasks.delete(id);
    else _expandedTasks.add(id);
    loadTasks();
  }
  async function loadChat() {
    try {
      await _loadChatInner();
    } catch (e) {
      console.warn("loadChat failed:", e);
    }
  }
  async function _loadChatInner() {
    const showEvents = document.getElementById("chatShowEvents").checked;
    const filterFrom = document.getElementById("chatFilterFrom").value;
    const filterTo = document.getElementById("chatFilterTo").value;
    const params = new URLSearchParams();
    if (!showEvents) params.set("type", "chat");
    const res = await fetch(
      "/messages" + (params.toString() ? "?" + params : "")
    );
    if (!res.ok) return;
    let msgs = await res.json();
    const senders = /* @__PURE__ */ new Set();
    const recipients = /* @__PURE__ */ new Set();
    for (const m of msgs) {
      if (m.type === "chat") {
        senders.add(m.sender);
        recipients.add(m.recipient);
      }
    }
    const fromSel = document.getElementById("chatFilterFrom");
    const toSel = document.getElementById("chatFilterTo");
    const prevFrom = fromSel.value;
    const prevTo = toSel.value;
    if (fromSel.options.length <= 1 || toSel.options.length <= 1) {
      fromSel.innerHTML = '<option value="">Anyone</option>' + [...senders].sort().map((n) => `<option value="${n}">${cap(n)}</option>`).join("");
      toSel.innerHTML = '<option value="">Anyone</option>' + [...recipients].sort().map((n) => `<option value="${n}">${cap(n)}</option>`).join("");
    }
    fromSel.value = prevFrom;
    toSel.value = prevTo;
    const between = document.getElementById("chatBetween").checked;
    if (filterFrom || filterTo) {
      msgs = msgs.filter((m) => {
        if (m.type === "event") return true;
        if (between && filterFrom && filterTo)
          return m.sender === filterFrom && m.recipient === filterTo || m.sender === filterTo && m.recipient === filterFrom;
        if (filterFrom && m.sender !== filterFrom) return false;
        if (filterTo && m.recipient !== filterTo) return false;
        return true;
      });
    }
    const chatMsgs = msgs.filter((m) => m.type === "chat");
    if (chatMsgs.length > 0) {
      const newestTs = chatMsgs[chatMsgs.length - 1].timestamp || "";
      if (_lastMsgTimestamp && newestTs > _lastMsgTimestamp && !_msgSendCooldown)
        playMsgSound();
      _lastMsgTimestamp = newestTs;
    }
    const log = document.getElementById("chatLog");
    const wasNearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 60;
    log.innerHTML = msgs.map((m) => {
      if (m.type === "event")
        return `<div class="msg-event"><span class="msg-event-line"></span><span class="msg-event-text">${esc(m.content)}</span><span class="msg-event-line"></span><span class="msg-event-time ts" data-ts="${m.timestamp}">${fmtTimestamp(m.timestamp)}</span></div>`;
      const c = avatarColor(m.sender);
      return `<div class="msg"><div class="msg-avatar" style="background:${c}">${avatarInitial(m.sender)}</div><div class="msg-body"><div class="msg-header"><span class="msg-sender" style="cursor:pointer" onclick="openAgentPanel('${m.sender}')">${cap(m.sender)}</span><span class="msg-recipient">\u2192 ${cap(m.recipient)}</span><span class="msg-time ts" data-ts="${m.timestamp}">${fmtTimestamp(m.timestamp)}</span></div><div class="msg-content">${esc(m.content)}</div></div></div>`;
    }).join("");
    if (wasNearBottom) log.scrollTop = log.scrollHeight;
    if (!_currentTeam) return;
    const agentsRes = await fetch("/teams/" + _currentTeam + "/agents");
    const agents = await agentsRes.json();
    const sel = document.getElementById("recipient");
    const prev = sel.value;
    const managers = agents.filter((a) => a.role === "manager");
    sel.innerHTML = managers.map(
      (a) => `<option value="${a.name}">${cap(a.name)} (${_currentTeam})</option>`
    ).join("");
    if (!sel.innerHTML)
      sel.innerHTML = agents.map((a) => `<option value="${a.name}">${cap(a.name)}</option>`).join("");
    if (prev) sel.value = prev;
    else if (managers.length) sel.value = managers[0].name;
  }
  async function loadAgents() {
    if (!_currentTeam) return;
    let res;
    try {
      res = await fetch("/teams/" + _currentTeam + "/agents");
    } catch (e) {
      return;
    }
    if (!res.ok) return;
    const agents = await res.json();
    const el = document.getElementById("agents");
    el.innerHTML = agents.map(
      (a) => `<div class="agent-card" data-name="${a.name}" onclick="openAgentPanel('${a.name}')">
    <span class="dot ${a.pid ? "dot-active" : "dot-idle"}"></span>
    <span class="agent-name">${cap(a.name)}</span>
    <span class="agent-status">${a.pid ? "Running (PID " + a.pid + ")" : "Idle"} \xB7 ${a.unread_inbox} unread</span>
  </div>`
    ).join("");
  }
  async function loadSidebar() {
    try {
      const [tasksRes, agentsRes] = await Promise.all([
        fetch("/tasks"),
        _currentTeam ? fetch("/teams/" + _currentTeam + "/agents") : Promise.resolve({ json: () => [] })
      ]);
      const tasks = await tasksRes.json();
      const agents = typeof agentsRes.json === "function" ? await agentsRes.json() : agentsRes;
      const statsMap = {};
      await Promise.all(
        (agents || []).map(async (a) => {
          try {
            const r = await fetch(
              "/teams/" + _currentTeam + "/agents/" + a.name + "/stats"
            );
            if (r.ok) statsMap[a.name] = await r.json();
          } catch (e) {
          }
        })
      );
      const now = /* @__PURE__ */ new Date();
      const oneDayAgo = new Date(now - 24 * 60 * 60 * 1e3);
      const doneToday = tasks.filter(
        (t) => t.completed_at && new Date(t.completed_at) > oneDayAgo && t.status === "done"
      ).length;
      const openCount = tasks.filter(
        (t) => t.status === "open" || t.status === "in_progress" || t.status === "review"
      ).length;
      let totalCost = 0;
      for (const name in statsMap)
        totalCost += statsMap[name].total_cost_usd || 0;
      document.getElementById("sidebarStatusContent").innerHTML = '<div class="sidebar-stat-row"><span class="stat-value">' + doneToday + ' done</span> &middot; <span class="stat-value">' + openCount + ' open</span></div><div class="sidebar-stat-row">$' + totalCost.toFixed(2) + " total spent</div>";
      const inProgressTasks = tasks.filter((t) => t.status === "in_progress");
      let agentHtml = "";
      for (const a of agents || []) {
        let dotClass = "dot-offline";
        let activity = "Idle";
        if (a.pid) {
          dotClass = "dot-working";
          const agentTask = inProgressTasks.find(
            (t) => t.assignee === a.name
          );
          activity = agentTask ? "T" + String(agentTask.id).padStart(4, "0") + " " + agentTask.title : "Working...";
        } else if (a.unread_inbox > 0) dotClass = "dot-queued";
        const cost = statsMap[a.name] ? "$" + Number(statsMap[a.name].total_cost_usd || 0).toFixed(2) : "";
        agentHtml += `<div class="sidebar-agent-row" style="cursor:pointer" onclick="openAgentPanel('` + a.name + `')"><span class="sidebar-agent-dot ` + dotClass + '"></span><span class="sidebar-agent-name">' + cap(a.name) + '</span><span class="sidebar-agent-activity">' + esc(activity) + '</span><span class="sidebar-agent-cost">' + cost + "</span></div>";
      }
      document.getElementById("sidebarAgentList").innerHTML = agentHtml;
      const sorted = [...tasks].sort((a, b) => {
        const da = a.updated_at || a.created_at || "";
        const db = b.updated_at || b.created_at || "";
        return db.localeCompare(da);
      }).slice(0, 7);
      let taskHtml = "";
      for (const t of sorted) {
        const tid = "T" + String(t.id).padStart(4, "0");
        taskHtml += '<div class="sidebar-task-row"><span class="sidebar-task-id">' + tid + '</span><span class="sidebar-task-title">' + esc(t.title) + '</span><span class="sidebar-task-badge"><span class="badge badge-' + t.status + '">' + fmtStatus(t.status) + '</span></span><span class="sidebar-task-assignee">' + (t.assignee ? cap(t.assignee) : "") + "</span></div>";
      }
      document.getElementById("sidebarTaskList").innerHTML = taskHtml;
    } catch (e) {
      console.error("Sidebar load error:", e);
    }
  }
  function renderDiffFiles() {
    const files = parse2(_diffRawText);
    if (!files.length)
      return '<div class="diff-empty">No files changed</div>';
    let html2 = '<div class="diff-file-list">';
    for (const f of files) {
      const name = f.newName || f.oldName || "unknown";
      html2 += `<div class="diff-file-list-item" onclick="switchDiffTab('diff')"><span class="diff-file-list-name">` + esc(name) + '</span><span class="diff-file-stats"><span class="diff-file-add">+' + f.addedLines + '</span><span class="diff-file-del">-' + f.deletedLines + "</span></span></div>";
    }
    return html2 + "</div>";
  }
  function renderDiffFull() {
    if (!_diffRawText)
      return '<div class="diff-empty">No changes</div>';
    return html(_diffRawText, {
      outputFormat: "line-by-line",
      drawFileList: false,
      matching: "lines"
    });
  }
  function switchDiffTab(tab) {
    _diffCurrentTab = tab;
    document.querySelectorAll(".diff-tab").forEach((t) => t.classList.toggle("active", t.dataset.dtab === tab));
    const body = document.getElementById("diffPanelBody");
    if (!_diffRawText && !_panelAgent) return;
    body.innerHTML = tab === "files" ? renderDiffFiles() : renderDiffFull();
  }
  async function openDiffPanel(taskId) {
    _panelMode = "diff";
    _panelAgent = null;
    _agentTabData = {};
    const panel = document.getElementById("diffPanel");
    const backdrop = document.getElementById("diffBackdrop");
    document.getElementById("diffPanelTitle").textContent = "T" + String(taskId).padStart(4, "0");
    document.getElementById("diffPanelBranch").textContent = "Loading...";
    document.getElementById("diffPanelCommits").innerHTML = "";
    document.getElementById("diffPanelCommits").style.display = "";
    const tabsEl = panel.querySelector(".diff-panel-tabs");
    tabsEl.innerHTML = `<button class="diff-tab active" data-dtab="files" onclick="switchDiffTab('files')">Files Changed</button><button class="diff-tab" data-dtab="diff" onclick="switchDiffTab('diff')">Full Diff</button>`;
    document.getElementById("diffPanelBody").innerHTML = '<div class="diff-empty">Loading diff...</div>';
    panel.classList.add("open");
    backdrop.classList.add("open");
    try {
      const res = await fetch("/tasks/" + taskId + "/diff");
      const data = await res.json();
      document.getElementById("diffPanelBranch").textContent = data.branch || "no branch";
      document.getElementById("diffPanelCommits").innerHTML = (data.commits || []).map(
        (c) => '<span class="diff-panel-commit">' + esc(String(c).substring(0, 7)) + "</span>"
      ).join("");
      _diffRawText = data.diff || "";
      _diffCurrentTab = "files";
      document.querySelectorAll(".diff-tab").forEach(
        (t) => t.classList.toggle("active", t.dataset.dtab === "files")
      );
      document.getElementById("diffPanelBody").innerHTML = renderDiffFiles();
    } catch (e) {
      document.getElementById("diffPanelBody").innerHTML = '<div class="diff-empty">Failed to load diff</div>';
    }
  }
  function closePanel() {
    document.getElementById("diffPanel").classList.remove("open");
    document.getElementById("diffBackdrop").classList.remove("open");
    _diffRawText = "";
    _panelMode = null;
    _panelAgent = null;
    _agentTabData = {};
  }
  function renderAgentInbox(msgs) {
    if (!msgs || !msgs.length)
      return '<div class="diff-empty">No messages</div>';
    return msgs.map(
      (m) => '<div class="agent-msg' + (m.read ? "" : " unread") + '"><div class="agent-msg-header"><span class="agent-msg-sender">' + esc(cap(m.sender)) + '</span><span class="agent-msg-time">' + fmtTimestamp(m.time) + `</span></div><div class="agent-msg-body collapsed" onclick="this.classList.toggle('collapsed')">` + esc(m.body) + "</div></div>"
    ).join("");
  }
  function renderAgentOutbox(msgs) {
    if (!msgs || !msgs.length)
      return '<div class="diff-empty">No messages</div>';
    return msgs.map(
      (m) => '<div class="agent-msg' + (m.routed ? "" : " pending") + '"><div class="agent-msg-header"><span class="agent-msg-sender">\u2192 ' + esc(cap(m.recipient)) + '</span><span class="agent-msg-time">' + fmtTimestamp(m.time) + `</span></div><div class="agent-msg-body collapsed" onclick="this.classList.toggle('collapsed')">` + esc(m.body) + "</div></div>"
    ).join("");
  }
  function renderAgentLogs(data) {
    const sessions = data && data.sessions ? data.sessions : [];
    if (!sessions.length)
      return '<div class="diff-empty">No worklogs</div>';
    return sessions.map(
      (s, i) => '<div class="agent-log-session"><div class="agent-log-header" onclick="toggleLogSession(this)"><span class="agent-log-arrow' + (i === 0 ? " expanded" : "") + '">\u25B6</span>' + esc(s.filename) + '</div><div class="agent-log-content' + (i === 0 ? " expanded" : "") + '">' + esc(s.content) + "</div></div>"
    ).join("");
  }
  function toggleLogSession(header) {
    header.querySelector(".agent-log-arrow").classList.toggle("expanded");
    header.nextElementSibling.classList.toggle("expanded");
  }
  function renderAgentStatsPanel(s) {
    if (!s)
      return '<div class="diff-empty">Stats unavailable</div>';
    return '<div class="agent-stats-grid"><div class="agent-stat"><div class="agent-stat-label">Tasks done</div><div class="agent-stat-value">' + s.tasks_done + '</div></div><div class="agent-stat"><div class="agent-stat-label">In review</div><div class="agent-stat-value">' + s.tasks_in_review + '</div></div><div class="agent-stat"><div class="agent-stat-label">Total tasks</div><div class="agent-stat-value">' + s.tasks_total + '</div></div><div class="agent-stat"><div class="agent-stat-label">Sessions</div><div class="agent-stat-value">' + s.session_count + '</div></div><div class="agent-stat"><div class="agent-stat-label">Tokens (in/out)</div><div class="agent-stat-value">' + fmtTokens(s.total_tokens_in, s.total_tokens_out) + '</div></div><div class="agent-stat"><div class="agent-stat-label">Total cost</div><div class="agent-stat-value">' + fmtCost(s.total_cost_usd) + '</div></div><div class="agent-stat"><div class="agent-stat-label">Agent time</div><div class="agent-stat-value">' + fmtElapsed(s.agent_time_seconds) + '</div></div><div class="agent-stat"><div class="agent-stat-label">Avg task time</div><div class="agent-stat-value">' + fmtElapsed(s.avg_task_seconds) + "</div></div></div>";
  }
  async function switchAgentTab(tab) {
    _agentCurrentTab = tab;
    document.querySelectorAll(".diff-tab").forEach((t) => t.classList.toggle("active", t.dataset.dtab === tab));
    const body = document.getElementById("diffPanelBody");
    const name = _panelAgent;
    if (!name) return;
    if (_agentTabData[tab]) {
      _renderAgentTab(tab, _agentTabData[tab]);
      return;
    }
    body.innerHTML = '<div class="diff-empty">Loading...</div>';
    try {
      const url = "/teams/" + _currentTeam + "/agents/" + name + "/" + tab;
      const res = await fetch(url);
      const data = await res.json();
      _agentTabData[tab] = data;
      _renderAgentTab(tab, data);
    } catch (e) {
      body.innerHTML = '<div class="diff-empty">Failed to load ' + tab + "</div>";
    }
  }
  function _renderAgentTab(tab, data) {
    const body = document.getElementById("diffPanelBody");
    if (tab === "inbox") body.innerHTML = renderAgentInbox(data);
    else if (tab === "outbox") body.innerHTML = renderAgentOutbox(data);
    else if (tab === "logs") body.innerHTML = renderAgentLogs(data);
    else if (tab === "stats") body.innerHTML = renderAgentStatsPanel(data);
  }
  async function openAgentPanel(agentName) {
    _panelMode = "agent";
    _panelAgent = agentName;
    _agentTabData = {};
    _agentCurrentTab = "inbox";
    _diffRawText = "";
    const panel = document.getElementById("diffPanel");
    const backdrop = document.getElementById("diffBackdrop");
    document.getElementById("diffPanelTitle").textContent = cap(agentName);
    document.getElementById("diffPanelBranch").textContent = "";
    document.getElementById("diffPanelCommits").innerHTML = "";
    document.getElementById("diffPanelCommits").style.display = "none";
    try {
      const r = await fetch("/teams/" + _currentTeam + "/agents");
      const agents = await r.json();
      const agent = agents.find((a) => a.name === agentName);
      if (agent)
        document.getElementById("diffPanelBranch").textContent = cap(
          agent.role
        );
    } catch (e) {
    }
    const tabsEl = panel.querySelector(".diff-panel-tabs");
    tabsEl.innerHTML = `<button class="diff-tab active" data-dtab="inbox" onclick="switchAgentTab('inbox')">Inbox</button><button class="diff-tab" data-dtab="outbox" onclick="switchAgentTab('outbox')">Outbox</button><button class="diff-tab" data-dtab="logs" onclick="switchAgentTab('logs')">Logs</button><button class="diff-tab" data-dtab="stats" onclick="switchAgentTab('stats')">Stats</button>`;
    document.getElementById("diffPanelBody").innerHTML = '<div class="diff-empty">Loading...</div>';
    panel.classList.add("open");
    backdrop.classList.add("open");
    switchAgentTab("inbox");
  }
  async function sendMsg() {
    if (_micActive && _recognition) {
      _recognition.stop();
      _micActive = false;
      const mb = document.getElementById("micBtn");
      if (mb) {
        mb.classList.remove("recording");
        mb.title = "Voice input";
      }
    }
    const input = document.getElementById("msgInput");
    const recipient = document.getElementById("recipient").value;
    if (!input.value.trim() || !_currentTeam) return;
    if (!recipient) {
      console.warn("No recipient selected");
      return;
    }
    _msgSendCooldown = true;
    setTimeout(function() {
      _msgSendCooldown = false;
    }, 4e3);
    try {
      const res = await fetch("/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          team: _currentTeam,
          recipient,
          content: input.value
        })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error("Send failed:", err.detail || res.statusText);
        return;
      }
      input.value = "";
      input.style.height = "auto";
    } catch (e) {
      console.error("Send error:", e);
    }
  }
  function autoResizeTextarea(el) {
    el.style.height = "auto";
    el.style.height = el.scrollHeight + "px";
  }
  function handleChatKeydown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMsg();
    }
  }
  (function initMic() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    const micBtn = document.getElementById("micBtn");
    micBtn.style.display = "flex";
    _recognition = new SpeechRecognition();
    _recognition.continuous = true;
    _recognition.interimResults = true;
    _recognition.lang = navigator.language || "en-US";
    _recognition.onresult = function(e) {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) _micFinalText += e.results[i][0].transcript;
        else interim += e.results[i][0].transcript;
      }
      const _el = document.getElementById("msgInput");
      _el.value = _micBaseText + _micFinalText + interim;
      autoResizeTextarea(_el);
    };
    _recognition.onend = function() {
      _micActive = false;
      _micStopping = false;
      micBtn.classList.remove("recording");
      micBtn.title = "Voice input";
    };
    _recognition.onerror = function(e) {
      if (e.error !== "aborted" && e.error !== "no-speech")
        console.warn("Speech recognition error:", e.error);
      _micActive = false;
      _micStopping = false;
      micBtn.classList.remove("recording");
      micBtn.title = "Voice input";
    };
  })();
  function toggleMic() {
    if (!_recognition || _micStopping) return;
    const micBtn = document.getElementById("micBtn");
    if (_micActive) {
      _micStopping = true;
      _recognition.stop();
      micBtn.classList.remove("recording");
      micBtn.title = "Voice input";
    } else {
      const input = document.getElementById("msgInput");
      _micBaseText = input.value ? input.value + " " : "";
      _micFinalText = "";
      try {
        _recognition.start();
      } catch (e) {
        return;
      }
      _micActive = true;
      micBtn.classList.add("recording");
      micBtn.title = "Stop recording";
    }
  }
  document.addEventListener("keydown", function(e) {
    if (e.key === "Escape") closePanel();
  });
  function refreshTimestamps() {
    document.querySelectorAll(".ts[data-ts]").forEach((el) => {
      el.textContent = fmtTimestamp(el.dataset.ts);
    });
  }
  setInterval(refreshTimestamps, 3e4);
  setInterval(() => {
    if (!_currentTeam || !_teams.length) loadTeams();
    loadSidebar();
    const active = document.querySelector(".panel.active");
    if (active && active.id === "chat") loadChat();
    if (active && active.id === "tasks") loadTasks();
    if (active && active.id === "agents") loadAgents();
  }, 2e3);
  function initFromHash() {
    const hash = window.location.hash.replace("#", "");
    const valid = ["chat", "tasks", "agents"];
    switchTab(valid.includes(hash) ? hash : "chat", false);
  }
  window.addEventListener("hashchange", () => {
    const hash = window.location.hash.replace("#", "");
    const valid = ["chat", "tasks", "agents"];
    if (valid.includes(hash)) switchTab(hash, false);
  });
  _updateMuteBtn();
  loadTeams().then(() => {
    initFromHash();
    loadSidebar();
  });
  Object.assign(window, {
    switchTab,
    onTeamChange,
    toggleMute,
    loadChat,
    loadTasks,
    sendMsg,
    handleChatKeydown,
    autoResizeTextarea,
    toggleMic,
    toggleTask,
    openDiffPanel,
    switchDiffTab,
    closePanel,
    openAgentPanel,
    switchAgentTab,
    toggleLogSession,
    approveTask,
    rejectTask,
    toggleRejectReason
  });
})();
//# sourceMappingURL=app.js.map
