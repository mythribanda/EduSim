import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

const projectSrc = path.resolve(process.cwd(), "src");

export async function resolve(specifier, context, defaultResolve) {
  if (specifier.startsWith("@/")) {
    const rel = specifier.slice(2);
    const absBase = path.join(projectSrc, rel);
    for (const ext of ["", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.js"]) {
      const candidate = absBase + ext;
      if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
        return defaultResolve(pathToFileURL(candidate).href, context);
      }
    }
  }
  if (specifier.startsWith("./") || specifier.startsWith("../")) {
    if (context.parentURL) {
      const parentDir = path.dirname(new URL(context.parentURL).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
      const target = path.resolve(parentDir, specifier);
      for (const ext of ["", ".ts", ".tsx", ".js", ".jsx"]) {
        const candidate = target + ext;
        if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) {
          return defaultResolve(pathToFileURL(candidate).href, context);
        }
      }
    }
  }
  return defaultResolve(specifier, context);
}
