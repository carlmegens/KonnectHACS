import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const {chromium}=createRequire(import.meta.url)('playwright');
const base=process.env.OUDERAPP_PREVIEW_URL||'http://127.0.0.1:8776/tests/frontend/index.html';
const browser=await chromium.launch({headless:true});
const page=await browser.newPage({viewport:{width:1100,height:1000}});
let passed=0;
async function test(name,fn){try{await fn();passed++;console.log(`PASS ${name}`);}catch(error){console.error(`FAIL ${name}`);throw error;}}
async function ready(query=''){await page.goto(base+query);await page.waitForFunction(()=>window.card && !card._loading && card._started);}
const count=(selector)=>page.locator(`ouderapp-card >> ${selector}`).count();
try {
 await test('real card renders feed, native controls, and authenticated photos',async()=>{
  for(const route of ['/README.md','/custom_components/ouderapp/api.py','/dist/OuderAppHACS-publish/README.md','/tests/frontend/test-card.mjs','/tests/frontend/artifacts/desktop-light.png']) {
   assert.equal((await page.request.get(new URL(route,base).href)).status(),404);
  }
  await ready();assert.equal(await count('article'),3);await page.waitForFunction(()=>card._urls.size>=2);
  assert.match(await page.locator('ouderapp-card >> h2').innerText(),/OuderApp/);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='timeline').length),1);
  assert.ok(await page.evaluate(()=>fixture.photoCalls.every(x=>/^\/api\/ouderapp\/example-account\/image\/timeline\/[A-Za-z0-9_-]{32}$/.test(x))));
  assert.ok(await page.locator('ouderapp-card >> .photo img').first().getAttribute('src').then(x=>x.startsWith('blob:')));
 });
 await test('calendar dates keep their day across timezones and timestamp labels follow DST',async()=>{
  for(const zone of ['America/Los_Angeles','Europe/Amsterdam','Pacific/Auckland']) {
   const context=await browser.newContext({timezoneId:zone});const localPage=await context.newPage();
   try {
    await localPage.goto(base+'?source=news');await localPage.waitForFunction(()=>window.card&&!card._loading&&card._started);
    await localPage.evaluate(async()=>{fixture.items=[{id:'0',title:'Datum zonder tijd',created_at:'2026-09-08',contents:'Voorbeeld',images:[]}];await card._load(true);});
    assert.equal(await localPage.locator('ouderapp-card >> time').innerText(),'8 sep 2026');
    assert.equal(await localPage.locator('ouderapp-card >> time').getAttribute('datetime'),'2026-09-08');
    assert.equal(await localPage.evaluate(()=>card._date('2026-09-08',true)),'8 sep 2026');
    assert.equal(await localPage.evaluate(()=>card._date('2026-02-30')),'');
    if(zone==='Europe/Amsterdam') {
     assert.match(await localPage.evaluate(()=>card._date('2026-03-29T00:30:00+00:00',true)),/01:30/);
     assert.match(await localPage.evaluate(()=>card._date('2026-03-29T01:30:00+00:00',true)),/03:30/);
    }
   } finally {await context.close();}
  }
 });
 await test('HA state updates never cause feed refetches',async()=>{
  const before=await page.evaluate(()=>fixture.calls.length);
  await page.evaluate(()=>{for(let i=0;i<100;i++)card.hass=makeHass();});
  assert.equal(await page.evaluate(()=>fixture.calls.length),before);
 });
 await test('keyboard expands message and photo, and restores focus on close',async()=>{
  const toggle=page.locator('ouderapp-card >> .toggle').first();await toggle.focus();await page.keyboard.press('Enter');
  assert.equal(await toggle.getAttribute('aria-expanded'),'true');
  assert.ok(await page.locator('ouderapp-card >> .body').first().innerText().then(x=>x.includes('Op vrijdag')));
  const photo=page.locator('ouderapp-card >> .photo').first();await photo.focus();await page.keyboard.press('Enter');
  assert.equal(await count('.enlarged'),1);await page.locator('ouderapp-card >> .close-photo').click();assert.equal(await count('.enlarged'),0);
  assert.equal(await photo.evaluate(el=>el.getRootNode().activeElement===el),true);
 });
 await test('untrusted message and title are text, never HTML',async()=>{
  await page.evaluate(async()=>{fixture.items=[{id:'attack',title:'<img src=x onerror="window.__xss=1">',contents:'<script>window.__xss=1</script><img src=x onerror="window.__xss=1">',images:[]}];await card._load(true);});
  assert.equal(await count('script'),0);assert.equal(await count('img'),0);assert.equal(await page.evaluate(()=>window.__xss),undefined);
  assert.ok(await page.locator('ouderapp-card >> .body').innerText().then(x=>x.includes('<script>')));
 });
 await test('account switching discards pending response data',async()=>{
  await page.goto(base+'?state=loading');await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.evaluate(()=>card.setConfig({...card._config,config_entry_id:'second-account'}));await page.waitForFunction(()=>fixture.deferred.length===2);
  await page.evaluate(()=>fixture.deferred[0].resolve({items:[{id:'old',title:'OLD ACCOUNT SECRET',contents:'private old',images:[]}],groups:[]}));
  await page.waitForTimeout(30);assert.ok(!(await page.locator('ouderapp-card >> ha-card').innerText()).includes('OLD ACCOUNT SECRET'));
  await page.evaluate(()=>fixture.deferred[1].resolve({items:[{id:'new',title:'NEW ACCOUNT',contents:'new visible',images:[]}],groups:[]}));
  await page.waitForFunction(()=>card._data?.items[0]?.id==='new');assert.ok((await page.locator('ouderapp-card >> ha-card').innerText()).includes('NEW ACCOUNT'));
 });
 await test('permission error clears content and revokes every photo URL',async()=>{
  await ready();await page.waitForFunction(()=>card._urls.size>=2);
  await page.evaluate(async()=>{fixture.state='unauthorized';await card._load(true);});
  assert.equal(await count('article'),0);assert.equal(await page.evaluate(()=>card._urls.size),0);assert.ok(await page.evaluate(()=>fixture.revoked.length>=2));
  assert.match(await page.locator('ouderapp-card >> ha-card').innerText(),/Geen toegang/);
 });
 await test('no account, expired login, empty and connection error are genuine states',async()=>{
  for(const [state,label] of [['noaccount','Geen toegankelijk'],['choose','Kies een'],['authentication_expired','Opnieuw aanmelden'],['empty','Geen items'],['cannot_connect','niet bereikbaar']]){
   await ready('?state='+state);assert.equal(await count('article'),0);assert.ok((await page.locator('ouderapp-card >> ha-card').innerText()).includes(label));
   assert.ok(!(await page.locator('ouderapp-card >> ha-card').innerText()).includes('private raw error'));
  }
 });
 await test('hidden document stops polling, drops data, and refreshes on return',async()=>{
  await ready();await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'));});
  assert.equal(await count('article'),0);const calls=await page.evaluate(()=>fixture.calls.length);
  await page.evaluate(()=>card._load(true));assert.equal(await page.evaluate(()=>fixture.calls.length),calls);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForFunction(()=>card._data?.items?.length===3);
 });
 await test('photo display and message requests remain bounded',async()=>{
  await ready();await page.evaluate(async()=>{fixture.items=Array.from({length:40},(_,i)=>({id:String(i),title:'Bounded announcement '+i,contents:'Synthetic',images:Array.from({length:100},(_,j)=>({id:`p${i}-${j}`.padEnd(32,'x'),name:'Synthetic'}))}));card.setConfig({...card._config,limit:20});});
  await page.waitForFunction(()=>card._data?.items?.length===20);assert.equal(await count('article'),20);assert.equal(await count('.photo'),12);
  assert.ok(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='timeline').every(x=>x.limit<=20)));
 });
 await test('image access revoked clears the feed',async()=>{
  await page.goto(base+'?state=loading');await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.evaluate(()=>{fixture.imageStatus=403;fixture.deferred[0].resolve({items:fixture.items,groups:fixture.groups});});
  await page.waitForFunction(()=>card._error==='unauthorized');assert.equal(await count('article'),0);assert.equal(await page.evaluate(()=>card._urls.size),0);
  const requests=await page.evaluate(()=>fixture.calls.length);await page.evaluate(()=>{for(let i=0;i<20;i++)card.hass=makeHass();});
  assert.equal(await page.evaluate(()=>fixture.calls.length),requests);
 });
 await test('visual editor changes settings through HA event contract',async()=>{
  await ready('?editor=1');await page.waitForFunction(()=>editor._accounts.length===2);
  const editor=page.locator('ouderapp-card-editor');
  await editor.locator('input#title').fill('Mijn school');await editor.locator('input#title').blur();
  assert.equal(await page.locator('ouderapp-card >> h2').innerText(),'Mijn school');
  await editor.locator('input#limit').fill('7');await editor.locator('input#limit').blur();assert.equal(await page.evaluate(()=>fixture.lastConfig.limit),7);
  await editor.locator('input[type=checkbox]').uncheck();await page.waitForFunction(()=>card._config.show_images===false);assert.equal(await count('.photo'),0);
 });
 await test('image fetches deduplicate while message expansion rerenders',async()=>{
  await ready('?state=empty');
  await page.evaluate(()=>{window.pendingPhotos=[];card._hass.fetchWithAuth=(url)=>new Promise(resolve=>pendingPhotos.push({url,resolve}));fixture.state='ready';card._load(true);});
  await page.waitForFunction(()=>pendingPhotos.length>=2);const requests=await page.evaluate(()=>pendingPhotos.length);
  await page.locator('ouderapp-card >> .toggle').first().click();await page.waitForTimeout(40);
  assert.equal(await page.evaluate(()=>pendingPhotos.length),requests);
 });
 await test('disconnect aborts ownership and releases memory',async()=>{
  await ready();await page.waitForFunction(()=>card._urls.size>=2);await page.evaluate(()=>card.remove());
  assert.equal(await page.evaluate(()=>card._data),null);assert.equal(await page.evaluate(()=>card._urls.size),0);
 });
 await test('conversation picker reads only the selected room and authenticates chat photos',async()=>{
  await ready('?source=messages');assert.equal(await count('article'),0);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='messages').length),0);
  assert.ok(await page.evaluate(()=>fixture.calls.some(x=>x.type==='ouderapp/accounts'&&x.source==='messages')));
  await page.locator('ouderapp-card >> #conversation').selectOption('101');await page.waitForFunction(()=>card._data?.items.length===2);await page.waitForFunction(()=>card._urls.size===1);
  assert.ok(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='messages').every(x=>x.conversation==='101'&&x.limit<=20)));
  assert.ok(await page.evaluate(()=>fixture.photoCalls.every(x=>/\/image\/messages\/[A-Za-z0-9_-]{32}$/.test(x))));
  const before=await page.evaluate(()=>fixture.calls.length);await page.evaluate(()=>{for(let i=0;i<20;i++)card.hass=makeHass();});assert.equal(await page.evaluate(()=>fixture.calls.length),before);
 });
 await test('late messages cannot cross a room or source change',async()=>{
  await ready('?source=messages');await page.evaluate(()=>fixture.pendingTypes=['messages']);
  await page.locator('ouderapp-card >> #conversation').selectOption('101');await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.evaluate(()=>card._selectRoom('202'));await page.waitForFunction(()=>fixture.deferred.length===2);
  await page.evaluate(()=>fixture.deferred[0].resolve({items:[{id:'1',contents:'OLD ROOM SECRET',images:[]}]}));
  await page.waitForTimeout(20);assert.equal(await count('article'),0);
  await page.evaluate(()=>{card.setConfig({...card._config,source:'timeline'});fixture.deferred[1].resolve({items:[{id:'2',contents:'OLD SOURCE SECRET',images:[]}]});});
  await page.waitForFunction(()=>card._data?.items[0]?.id==='m1');assert.ok(!(await page.locator('ouderapp-card >> ha-card').innerText()).includes('SECRET'));
 });
 await test('chat permissions are separate and revocation removes room titles and photos',async()=>{
  await ready('?source=messages&room=101');await page.waitForFunction(()=>card._urls.size===1);
  await page.evaluate(async()=>{fixture.chatAllowed=false;await card._load(true);});
  assert.equal(await count('article'),0);assert.equal(await page.evaluate(()=>card._conversations.length),0);assert.equal(await page.evaluate(()=>card._urls.size),0);
  assert.ok(!(await page.locator('ouderapp-card >> ha-card').innerText()).includes('Contact met'));
  await page.evaluate(()=>card.setConfig({...card._config,source:'timeline'}));await page.waitForFunction(()=>card._data?.items.length===3);
 });
 await test('message editor selects source and room without reading every conversation',async()=>{
  await ready('?editor=1');await page.waitForFunction(()=>editor._accounts.length===2);
  await page.locator('ouderapp-card-editor >> #source').selectOption('messages');await page.waitForFunction(()=>editor._groups[0]?.id==='101');
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='messages').length),0);
  await page.locator('ouderapp-card-editor >> #chatroom_id').selectOption('202');await page.waitForFunction(()=>card._data?.items[0]?.id==='2001');
  assert.equal(await page.evaluate(()=>fixture.lastConfig.source),'messages');assert.equal(await page.evaluate(()=>fixture.lastConfig.chatroom_id),'202');
  assert.ok(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='messages').every(x=>x.conversation==='202')));
 });
 await test('HA more-info properties select content and clear on entity change',async()=>{
  await ready('?surface=popup&source=messages');assert.equal(await page.evaluate(()=>card._config.source),'messages');assert.equal(await count('article'),0);
  await page.locator('more-info-ouderapp >> #conversation').selectOption('101');await page.waitForFunction(()=>card._urls.size===1);
  const before=await page.evaluate(()=>fixture.calls.length);await page.evaluate(()=>{for(let i=0;i<20;i++){surface.hass=makeHass();surface.stateObj={...surface._stateObj,state:String(i)};}});assert.equal(await page.evaluate(()=>fixture.calls.length),before);
  assert.match(await page.locator('more-info-ouderapp >> .surface-link a').getAttribute('href'),/^\/ouderapp\/example-account\?source=messages$/);
  await page.evaluate(()=>surface.stateObj={attributes:{ouderapp_config_entry_id:'second-account',ouderapp_source:'timeline'}});
  assert.equal(await page.evaluate(()=>card._urls.size),0);await page.waitForFunction(()=>card._data?.items.length===3);
  assert.equal(await page.evaluate(()=>card._config.config_entry_id),'second-account');
 });
 await test('popup retains picker and refresh focus without stealing it after loading',async()=>{
  await ready('?surface=popup&source=messages');
  const picker=page.locator('ouderapp-card >> #conversation');await picker.focus();await picker.selectOption('101');
  await page.waitForFunction(()=>card._data?.items.length===2&&!card._loading);
  assert.equal(await picker.evaluate(el=>el.getRootNode().activeElement===el),true);
  const refresh=page.locator('ouderapp-card >> #refresh');await refresh.focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>!card._loading);
  assert.equal(await refresh.evaluate(el=>el.getRootNode().activeElement===el),true);
  await page.evaluate(()=>fixture.pendingTypes=['messages']);await picker.focus();await picker.selectOption('202');
  await page.waitForFunction(()=>fixture.deferred.length===1);
  const link=page.locator('more-info-ouderapp >> .surface-link a');await link.focus();
  await page.evaluate(()=>fixture.deferred[0].resolve({items:fixture.chatItems['202']}));
  await page.waitForFunction(()=>card._data?.items[0]?.id==='2001'&&!card._loading);
  assert.equal(await link.evaluate(el=>el.getRootNode().activeElement===el),true);
 });
 await test('hidden panel uses route account, native tabs and device backlink',async()=>{
  await ready('?surface=panel');assert.equal(await page.evaluate(()=>card._config.config_entry_id),'example-account');
  assert.equal(await page.locator('ouderapp-panel >> .panel-toolbar a').getAttribute('href'),'/config/devices/device/synthetic-device');
  await page.locator('ouderapp-panel >> #tab-timeline').focus();await page.keyboard.press('End');await page.waitForFunction(()=>card._error==='chooseConversation');
  assert.equal(await page.locator('ouderapp-panel >> #tab-messages').getAttribute('aria-selected'),'true');
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='ouderapp/content'&&x.kind==='messages').length),0);
  await page.locator('ouderapp-panel >> #conversation').selectOption('202');await page.waitForFunction(()=>card._data?.items[0]?.id==='2001');
  await page.evaluate(()=>surface.route={path:'/second-account'});await page.waitForFunction(()=>card._config.config_entry_id==='second-account'&&!card._loading);
  assert.equal(await count('article'),0);assert.equal(await page.locator('ouderapp-panel >> .panel-toolbar a').getAttribute('href'),'/config/integrations/integration/ouderapp');
 });
 await test('panel can choose an authorized account when route has none',async()=>{
  await ready('?surface=panel&chooseAccount=1');await page.waitForFunction(()=>surface._accounts.length===2);
  await page.locator('ouderapp-panel >> #panel-account').selectOption('example-account');await page.waitForFunction(()=>card._data?.items.length===3);
  assert.equal(await page.evaluate(()=>card._config.config_entry_id),'example-account');
 });
 await test('message empty and missing-room states never invent content',async()=>{
  for(const [query,label] of [['?source=messages&state=noConversations','Geen gesprekken'],['?source=messages&room=101&state=empty','Geen berichten'],['?source=messages&room=999','Gesprek niet beschikbaar']]) {
   await ready(query);assert.equal(await count('article'),0);assert.ok((await page.locator('ouderapp-card >> ha-card').innerText()).includes(label));
  }
  await ready('?source=messages');await page.locator('ouderapp-card >> #conversation').selectOption('101');await page.waitForFunction(()=>card._data?.items.length===2);
  await page.evaluate(()=>card.hass=makeHass('another-user'));await page.waitForFunction(()=>card._error==='chooseConversation');assert.equal(await count('article'),0);
 });
 await test('all panel sources route to correct content with keyboard controls',async()=>{
  await ready('?surface=panel');
  for (const source of ['news','newsletters','timeline']) {
   await page.locator(`ouderapp-panel >> #tab-${source}`).click();
   await page.waitForFunction(source=>card._config.source===source&&!card._loading,source);
   assert.ok(await page.evaluate(source=>fixture.calls.some(call=>call.type==='ouderapp/content'&&call.kind===source),source));
  }
  await page.locator('ouderapp-panel >> #tab-timeline').focus(); await page.keyboard.press('ArrowRight');
  assert.equal(await page.locator('ouderapp-panel >> #tab-news').getAttribute('aria-selected'),'true');
 });
 await test('news and newsletter text loads only on expansion, stays plain, and preserves keyboard focus',async()=>{
  for(const source of ['news','newsletters']) {
   await ready('?source='+source);
   await page.evaluate(async()=>{fixture.items=[{id:'0',article_id:'42',title:'Nieuwsbericht',contents:'Korte voorvertoning',images:[]}];await card._load(true);});
   assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.article).length),0);
   const toggle=page.locator('ouderapp-card >> .toggle').first();await toggle.focus();await page.keyboard.press('Enter');
   await page.waitForFunction(()=>Array.from(card._articles.values())[0]?.value);
   assert.match(await page.locator('ouderapp-card >> .body').innerText(),/Volledige tekst/);
   assert.equal(await toggle.evaluate(el=>el.getRootNode().activeElement===el),true);
   await toggle.click();await toggle.click();assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.article).length),1);
   await page.evaluate(()=>{Array.from(card._articles.values())[0].stale=true;Array.from(card._articles.values())[0].value.truncated=true;Array.from(card._articles.values())[0].value.contents='<img src=x onerror="window.__xss=1">';card._render();});
   assert.equal(await count('img'),0);assert.equal(await page.evaluate(()=>window.__xss),undefined);
   const notice=await page.locator('ouderapp-card >> article').innerText();assert.match(notice,/ingekort/);assert.match(notice,/eerder opgehaalde/);
  }
 });
 await test('article errors allow retry and late results cannot cross account changes or closure',async()=>{
  await ready('?source=news');
  await page.evaluate(async()=>{fixture.items=[{id:'0',article_id:'42',title:'Detail',contents:'Preview',images:[]}];fixture.articleError='cannot_connect';await card._load(true);});
  await page.locator('ouderapp-card >> .toggle').click();await page.waitForFunction(()=>Array.from(card._articles.values())[0]?.error);
  assert.match(await page.locator('ouderapp-card >> ha-card').innerText(),/kon niet worden opgehaald/);
  await page.evaluate(()=>{fixture.articleError=null;fixture.articlePending=true;});
  await page.locator('ouderapp-card >> .text-button').click();await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.locator('ouderapp-card >> .toggle').click();
  await page.evaluate(()=>fixture.deferred[0].resolve({detail:true,items:[{article_id:'42',contents:'Secret detail',images:[]}]}));
  await page.waitForFunction(()=>Array.from(card._articles.values())[0]?.value);
  assert.ok(!(await page.locator('ouderapp-card >> ha-card').innerText()).includes('Secret detail'));
  await page.evaluate(async()=>{await card._load(true);});await page.locator('ouderapp-card >> .toggle').click();
  await page.waitForFunction(()=>fixture.deferred.length===2);
  await page.evaluate(()=>card.setConfig({...card._config,config_entry_id:'second-account'}));
  await page.waitForFunction(()=>!card._loading);
  await page.evaluate(()=>fixture.deferred[1].resolve({detail:true,items:[{article_id:'42',contents:'OLD ACCOUNT SECRET',images:[]}]}));
  await page.waitForTimeout(40);assert.equal(await page.evaluate(()=>card._articles.size),0);
  assert.ok(!(await page.locator('ouderapp-card >> ha-card').innerText()).includes('OLD ACCOUNT SECRET'));
 });
 await test('news detail photos load on expansion, revoke on collapse and reject late photo results',async()=>{
  await ready('?source=news');
  await page.evaluate(async()=>{fixture.items=[{id:'0',article_id:'42',title:'Nieuws met foto',contents:'Preview',images:[]}];fixture.articleImages=[{id:'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',name:'Nieuwsfoto'}];await card._load(true);fixture.photoCalls=[];});
  assert.equal(await count('.photo'),0);assert.equal(await page.evaluate(()=>fixture.photoCalls.length),0);
  await page.locator('ouderapp-card >> .toggle').click();await page.waitForFunction(()=>card._urls.size===1);
  assert.equal(await count('.photo img'),1);assert.match(await page.locator('ouderapp-card >> .photo img').getAttribute('src'),/^blob:/);
  assert.match(await page.evaluate(()=>fixture.photoCalls[0]),/image\/timeline\//);
  await page.locator('ouderapp-card >> .toggle').click();assert.equal(await count('.photo'),0);assert.equal(await page.evaluate(()=>card._urls.size),0);
  assert.ok(await page.evaluate(()=>fixture.revoked.length>0));
  await page.evaluate(()=>fixture.photoPending=true);await page.locator('ouderapp-card >> .toggle').click();await page.waitForFunction(()=>fixture.photoDeferred.length===1);
  await page.locator('ouderapp-card >> .toggle').click();await page.evaluate(()=>fixture.photoDeferred[0]());await page.waitForFunction(()=>card._loadingPhotoIds.size===0);
  assert.equal(await page.evaluate(()=>card._urls.size),0);assert.equal(await count('.photo'),0);
  await page.evaluate(()=>{fixture.photoPending=false;card.setConfig({...card._config,show_images:false});});await page.waitForFunction(()=>!card._loading);await page.locator('ouderapp-card >> .toggle').click();await page.waitForFunction(()=>Array.from(card._articles.values())[0]?.value);
  assert.equal(await count('.photo'),0);
 });
 await test('article access revocation clears the entire visible feed',async()=>{
  await ready('?source=newsletters');
  await page.evaluate(async()=>{fixture.items=[{id:'0',article_id:'42',title:'Private newsletter',contents:'Private preview',images:[]}];fixture.articleError='unauthorized';await card._load(true);});
  await page.locator('ouderapp-card >> .toggle').click();await page.waitForFunction(()=>card._error==='unauthorized');
  assert.equal(await count('article'),0);assert.equal(await page.evaluate(()=>card._articles.size),0);
 });
 await test('planning tab is admin-only and reads only after an explicit action',async()=>{
  await ready('?surface=panel');assert.equal(await page.locator('ouderapp-panel >> #tab-planning').count(),0);
  await page.evaluate(()=>surface.route={path:'/example-account?source=planning'});assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='call_service').length),0);
  await ready('?surface=panel&admin=1');await page.locator('ouderapp-panel >> #tab-timeline').focus();await page.keyboard.press('End');
  await page.waitForFunction(()=>surface._source==='planning');await page.evaluate(()=>window.planning=surface._planning);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='call_service').length),0);
  assert.equal(await page.locator('ouderapp-planning >> #planning-download').isDisabled(),true);
  const load=page.locator('ouderapp-planning >> #planning-load');await load.focus();await page.keyboard.press('Enter');await page.waitForFunction(()=>planning._data&&!planning._busy);
  assert.equal(await page.locator('ouderapp-planning >> .slot').count(),2);
  const text=await page.locator('ouderapp-planning >> ha-card').innerText();assert.match(text,/Voorlopig/);assert.match(text,/Afwezig/);assert.match(text,/Bevestiging vereist/);
  assert.equal(await load.evaluate(el=>el.getRootNode().activeElement===el),true);
  const countBefore=await page.evaluate(()=>fixture.calls.length);await page.evaluate(()=>{for(let i=0;i<20;i++)surface.hass=makeHass();});assert.equal(await page.evaluate(()=>fixture.calls.length),countBefore);
  const downloadEvent=page.waitForEvent('download');await page.locator('ouderapp-planning >> #planning-download').click();const download=await downloadEvent;
  assert.match(download.suggestedFilename(),/^ouderapp-[0-9-]+\.ics$/);
  const textFile=await (await import('node:fs/promises')).readFile(await download.path(),'utf8');assert.match(textFile,/^BEGIN:VCALENDAR\r\n/);
  assert.equal(await page.evaluate(()=>fixture.calls.filter(x=>x.type==='call_service').at(-1).service_data.format),'ics');
  await page.waitForFunction(()=>!planning._url);assert.ok(await page.evaluate(()=>fixture.revoked.length>0));
 });
 await test('planned attendance has a clear label without hiding required confirmation',async()=>{
  await ready('?surface=panel&admin=1');await page.locator('ouderapp-panel >> #tab-planning').click();
  await page.evaluate(()=>{window.planning=surface._planning;fixture.planningStatus='attend';});
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>planning._data);
  const row=page.locator('ouderapp-planning >> .slot').first();assert.match(await row.innerText(),/Gepland/);assert.match(await row.innerText(),/Bevestiging vereist/);assert.doesNotMatch(await row.innerText(),/Status onbekend/);
  await page.evaluate(()=>fixture.planningStatus='future-status');await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>planning._data?.events[0].status==='future-status');assert.match(await row.innerText(),/Status onbekend/);
 });
 await test('planning period edits and account changes discard pending data',async()=>{
  await ready('?surface=panel&admin=1');await page.locator('ouderapp-panel >> #tab-planning').click();await page.evaluate(()=>{window.planning=surface._planning;fixture.planningPending=true;});
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.locator('ouderapp-planning >> #planning-end').fill('2100-12-31');await page.locator('ouderapp-planning >> #planning-end').press('Tab');
  await page.evaluate(()=>fixture.deferred[0].resolve({response:{events:[{child:'OLD PERIOD SECRET'}]}}));await page.waitForTimeout(30);assert.equal(await page.evaluate(()=>planning._data),null);
  await page.locator('ouderapp-planning >> #planning-load').click();assert.match(await page.locator('ouderapp-planning >> [role=alert]').innerText(),/31 dagen/);
  assert.equal(await page.evaluate(()=>fixture.deferred.length),1);
  await page.evaluate(()=>{planning._end=new Date(Date.parse(planning._start)+7*86400000).toISOString().slice(0,10);planning._render();});
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>fixture.deferred.length===2);
  await page.evaluate(()=>surface.route={path:'/second-account?source=planning'});
  await page.evaluate(()=>fixture.deferred[1].resolve({response:{events:[{child:'OLD ACCOUNT SECRET'}]}}));await page.waitForTimeout(30);
  assert.equal(await page.evaluate(()=>planning._account),'second-account');assert.equal(await page.evaluate(()=>planning._data),null);
  assert.doesNotMatch(await page.locator('ouderapp-planning >> ha-card').innerText(),/SECRET/);
 });
 await test('planning errors and incomplete results disable download and hide provider messages',async()=>{
  await ready('?surface=panel&admin=1');await page.locator('ouderapp-panel >> #tab-planning').click();await page.evaluate(()=>{window.planning=surface._planning;fixture.planningError=true;});
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>planning._error);
  assert.doesNotMatch(await page.locator('ouderapp-planning >> ha-card').innerText(),/PRIVATE-RAW/);
  for(const flag of ['planningOffline','planningTruncated','planningEmpty']) {
   await page.evaluate(flag=>{fixture.planningError=false;fixture.planningOffline=false;fixture.planningTruncated=false;fixture.planningEmpty=false;fixture[flag]=true;},flag);
   await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>planning._data&&!planning._busy);
   assert.equal(await page.locator('ouderapp-planning >> #planning-download').isDisabled(),true);
   const text=await page.locator('ouderapp-planning >> ha-card').innerText();assert.match(text,flag==='planningOffline'?/offline/:flag==='planningTruncated'?/100 momenten/:/Geen opvangmomenten/);
  }
 });
 await test('planning parent hidden during a request cannot retain its response',async()=>{
  await ready('?surface=panel&admin=1');await page.locator('ouderapp-panel >> #tab-planning').click();await page.evaluate(()=>{window.planning=surface._planning;fixture.planningPending=true;});
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.evaluate(()=>surface.style.display='none');await page.waitForFunction(()=>!planning._busy);
  await page.evaluate(()=>fixture.deferred[0].resolve({response:{events:[{child:'HIDDEN SECRET'}]}}));await page.waitForTimeout(30);assert.equal(await page.evaluate(()=>planning._data),null);
  await page.evaluate(()=>surface.style.display='');assert.equal(await page.locator('ouderapp-planning >> .slot').count(),0);
 });
 await test('hidden planning, tab closure and admin revocation clear private state',async()=>{
  await ready('?surface=panel&admin=1');await page.locator('ouderapp-panel >> #tab-planning').click();await page.evaluate(()=>window.planning=surface._planning);
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>planning._data);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'hidden'});document.dispatchEvent(new Event('visibilitychange'));});
  assert.equal(await page.evaluate(()=>planning._data),null);assert.equal(await page.locator('ouderapp-planning >> .slot').count(),0);
  await page.evaluate(()=>{Object.defineProperty(document,'visibilityState',{configurable:true,value:'visible'});document.dispatchEvent(new Event('visibilitychange'));fixture.planningPending=true;});
  await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>fixture.deferred.length===1);
  await page.locator('ouderapp-panel >> #tab-news').click();await page.evaluate(()=>fixture.deferred[0].resolve({response:{events:[{child:'LATE SECRET'}]}}));await page.waitForTimeout(30);assert.equal(await page.evaluate(()=>planning._data),null);
  await page.locator('ouderapp-panel >> #tab-planning').click();await page.evaluate(()=>fixture.planningPending=false);await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>planning._data);
  await page.evaluate(()=>{fixture.admin=false;surface.hass=makeHass();});assert.equal(await page.evaluate(()=>planning._data),null);assert.equal(await page.locator('ouderapp-panel >> #tab-planning').count(),0);
 });
 if(!process.env.OUDERAPP_SKIP_SCREENSHOTS) {
 // One batched visual inspection: desktop/light + mobile/dark + editor + loading/error.
 const artifacts=new URL('./artifacts/',import.meta.url);await mkdir(artifacts,{recursive:true});
 for(const shot of [
  {name:'planning-desktop',width:1100,height:1000,query:'?surface=panel&admin=1',planning:true},
  {name:'planning-mobile',width:390,height:1100,query:'?surface=panel&admin=1&theme=dark',planning:true},
  {name:'newsletter-detail-desktop',width:1100,height:950,query:'?source=newsletters',article:true},
  {name:'news-detail-mobile',width:390,height:950,query:'?source=news&theme=dark',article:true},
  {name:'desktop-light',width:1100,height:1050,query:''},
  {name:'mobile-dark',width:390,height:1000,query:'?theme=dark'},
  {name:'messages-desktop',width:1100,height:950,query:'?source=messages&room=101'},
  {name:'messages-mobile',width:390,height:950,query:'?source=messages&room=101&theme=dark'},
  {name:'popup',width:700,height:950,query:'?surface=popup&source=messages',selectRoom:'101'},
  {name:'panel-mobile',width:390,height:950,query:'?surface=panel&theme=dark'},
  {name:'panel',width:1000,height:1100,query:'?surface=panel&source=messages',selectRoom:'101'},
  {name:'editor',width:800,height:1500,query:'?editor=1'},
  {name:'loading',width:390,height:700,query:'?state=loading'},
  {name:'error',width:390,height:700,query:'?state=authentication_expired&lang=en'},
 ]) {
  await page.setViewportSize({width:shot.width,height:shot.height});await page.goto(base+shot.query);
  if(shot.name!=='loading')await page.waitForFunction(()=>card._started&&!card._loading);
  if(shot.article){await page.evaluate(async()=>{fixture.items=[{id:"0",article_id:"42",title:"Samen naar de bibliotheek",contents:"Deze week bezoeken we met de groep de bibliotheek.",images:[]}];if(card._config.source==='news')fixture.articleImages=[{id:'eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',name:'Synthetische nieuwsfoto'}];await card._load(true);});await page.locator("ouderapp-card >> .toggle").click();await page.waitForFunction(()=>Array.from(card._articles.values())[0]?.value);}
  if(shot.planning){await page.evaluate(()=>fixture.planningStatus='attend');await page.locator('ouderapp-panel >> #tab-planning').click();await page.locator('ouderapp-planning >> #planning-load').click();await page.waitForFunction(()=>surface._planning._data);}
  if(shot.selectRoom){await page.locator('ouderapp-card >> #conversation').selectOption(shot.selectRoom);await page.waitForFunction(()=>card._data?.items.length>0);}
  await page.waitForTimeout(100);await page.screenshot({path:new URL(shot.name+'.png',artifacts).pathname,fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`No horizontal overflow: ${shot.name}`);
 }
 }
 console.log(`${passed} functional checks passed.`);
} finally {await browser.close();}
