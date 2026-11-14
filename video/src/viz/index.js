// The visual-technique library, by name (blogwriter/vizlib.py declares the same names and their fields).
import {CHARTS} from "./charts";
import {SYSTEMS1} from "./systems1";
import {SYSTEMS2} from "./systems2";
import {ML} from "./ml";
import {EXPLAIN} from "./explain";
import {DATA} from "./data";
import {AI} from "./ai";
import {OPS} from "./ops";
import {PATTERNS} from "./patterns";

export const VIZ = {...CHARTS, ...SYSTEMS1, ...SYSTEMS2, ...ML, ...EXPLAIN, ...DATA, ...AI, ...OPS, ...PATTERNS};
