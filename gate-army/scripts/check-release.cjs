const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),p=JSON.parse(fs.readFileSync(path.join(root,'release/publisher.json'),'utf8'));
const blocked=[];
for(const key of ['country','websiteUrl','privacyPolicyUrl','admobPublisherId'])if(!p[key])blocked.push('Provide '+key);
for(const key of ['playAccountVerified','admobAccountApproved','umpMessagesPublished','appAdsTxtVerified','androidDeviceTested','closedTestingRequirementSatisfied','dataSafetyReviewed','contentRatingCompleted'])if(!p[key])blocked.push('Complete '+key);
if(!fs.existsSync(path.join(root,'android/release.properties')))blocked.push('Configure your production AdMob IDs and privacy URL in android/release.properties');
if(!fs.existsSync(path.join(root,'android/app/build/outputs/bundle/release/app-release.aab')))blocked.push('Build and verify the signed Android App Bundle');
if(!fs.existsSync(path.join(root,'release/screenshots/phone-01.png')))blocked.push('Capture store screenshots from the tested Android build');
if(blocked.length){console.log('NOT READY TO PUBLISH\n'+blocked.map(v=>'• '+v).join('\n'));process.exitCode=1;}else console.log('Local checklist complete. Review the actual Play Console declarations and signed artifact before submission.');
