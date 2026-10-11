// Runs our pure public scorer against a synthetic input supplied on stdin.
// No browser automation, network, storage or private files are involved.
const fs=require('node:fs'), vm=require('node:vm');
const source=fs.readFileSync('web/assets/app.js','utf8');
const state=JSON.parse(fs.readFileSync(0,'utf8'));
const scorer=source.slice(source.indexOf('function rescoreDemo()'),source.indexOf('async function api('));
const sandbox={state,demoMetrics:()=>{},console};
vm.createContext(sandbox);vm.runInContext(scorer+';rescoreDemo()',sandbox);
process.stdout.write(JSON.stringify(state.jobs.map(j=>({id:j.id,score:j.matching.score,action:j.matching.action}))));
