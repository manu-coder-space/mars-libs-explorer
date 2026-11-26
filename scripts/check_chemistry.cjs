/* Check scientific endmembers and invalid-input behavior independently of the UI. */
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const scope={window:{},document:{}};
vm.runInNewContext(fs.readFileSync('dist/atlas.js','utf8'),scope);
const {metric,ternary}=scope.window.MarsChemistry;
const mw={SiO2:60.0843,Al2O3:101.9613,FeOT:71.844,MgO:40.3044,CaO:56.0774,Na2O:61.9789,K2O:94.196};
function point(moles){const oxides={};for(const k of Object.keys(mw))oxides[k]=(moles[k]||0)*mw[k];return{oxides};}
function close(a,b){assert.ok(Math.abs(a-b)<1e-10,`${a} ≠ ${b}`);}
const forsterite=point({SiO2:1,MgO:2});close(metric(forsterite,'mg_number'),100);close(metric(forsterite,'mafic_si'),2);close(ternary(forsterite).a,1/3);close(ternary(forsterite).c,2/3);
const fayalite=point({SiO2:1,FeOT:2});close(metric(fayalite,'mg_number'),0);close(metric(fayalite,'mafic_si'),2);
const diopside=point({SiO2:2,CaO:1,MgO:1});close(metric(diopside,'mafic_si'),1);close(ternary(diopside).a,.5);close(ternary(diopside).b,.25);close(ternary(diopside).c,.25);
const albite=point({SiO2:3,Al2O3:.5,Na2O:.5});close(metric(albite,'al_si'),1/3);close(ternary(albite).a,.8);close(ternary(albite).b,.2);
const anorthite=point({SiO2:2,Al2O3:1,CaO:1});close(metric(anorthite,'al_si'),1);close(ternary(anorthite).a,.8);
const jadeite=point({SiO2:2,Al2O3:.5,Na2O:.5});close(metric(jadeite,'mafic_si'),0); // Hence qualified 'common Ca–Mg–Fe pyroxenes'.
const scaled={oxides:Object.fromEntries(Object.entries(diopside.oxides).map(([k,v])=>[k,v*1.27]))};close(metric(scaled,'mafic_si'),1);close(ternary(scaled).c,.25);
const missing=point({SiO2:1,MgO:1});missing.oxides.Al2O3=null;assert.equal(ternary(missing),null);close(metric(missing,'mg_number'),100);
const negative=point({SiO2:1,MgO:1});negative.oxides.FeOT=-.1;assert.equal(metric(negative,'mg_number'),null);assert.equal(ternary(negative),null);
assert.equal(metric(point({MgO:1}),'mafic_si'),null);assert.equal(metric(point({SiO2:1}),'mg_number'),null);assert.equal(ternary(point({})),null);
console.log('Scientific ratio checks passed: olivine, pyroxenes, feldspars, scale invariance, missing/negative/zero-denominator cases.');
