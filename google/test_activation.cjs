'use strict';
const assert=require('assert'), fs=require('fs'), vm=require('vm');
const props={}; let identity='harshad422@gmail.com', installed=0, exported=0, written;
const sandbox={
  OWNER_EMAIL_DEFAULT:'harshad422@gmail.com',
  RADAR_DEPLOYMENT_CONFIG:{OWNER_EMAIL:'harshad422@gmail.com',SHEET_ID:'owned-sheet'},
  Session:{getEffectiveUser:()=>({getEmail:()=>identity})},
  withScriptLock:f=>f(),getProp:k=>props[k],setProp:(k,v)=>{props[k]=v;},
  getOwnerEmail:()=>props.OWNER_EMAIL,getOrCreateDriveTree:()=>({root:'owned-folder'}),
  getOrCreateSpreadsheet:()=>({}),installRadarTriggers:()=>{installed++;},
  exportSnapshot:()=>{exported++;},writeJsonFile:(folder,name,value)=>{written={folder,name,value};},
  ScriptApp:{getProjectTriggers:()=>['dispatchRadar','processGmailReplies'].map(handler=>({getHandlerFunction:()=>handler,getUniqueId:()=>handler+'-id'}))}
};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync('google/Activate.js','utf8'),sandbox);
identity='someone@example.com';assert.throws(()=>sandbox.activateRadar(),/Only the configured/);assert.equal(installed,0);
identity='harshad422@gmail.com';const result=sandbox.activateRadar();
assert.equal(result.reply_ratings_active,true);assert.equal(result.delivery_dispatcher_active,true);
assert.equal(written.name,'activation-status.json');assert.equal(exported,1);
sandbox.activateRadar();assert.equal(installed,2);
props.SHEET_ID='different-sheet';assert.throws(()=>sandbox.activateRadar(),/configuration differs/);assert.equal(installed,2);
console.log('Owner-only activation, status export and configuration preservation passed.');
