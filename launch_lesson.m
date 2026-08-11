function launch_lesson(moduleRef)
%LAUNCH_LESSON Open one implemented lesson and its interactive controls.
arguments
    moduleRef = "P01"
end
root = fileparts(mfilename('fullpath'));
manifest = jsondecode(fileread(fullfile(root,'curriculum','modules.json')));
module = resolveModule(manifest.modules,moduleRef);
if ~strcmp(module.status,'implemented')
    error('%s is scaffolded. Implement its governed batch before tutor use.',module.id);
end
folder = fullfile(root,module.folder);
addpath(folder,'-begin');
clear model interactive;
cleanup = onCleanup(@() rmpath(folder)); %#ok<NASGU>
fprintf('%s - %s\n%s\n',module.id,module.title,module.guiding_question);
run(fullfile(folder,'lesson.m'));
end

function module = resolveModule(modules,moduleRef)
key = upper(string(moduleRef));
for k = 1:numel(modules)
    candidates = [upper(string(modules(k).id)), string(modules(k).number), ...
        sprintf('%02d',modules(k).number), upper(string(modules(k).slug))];
    if any(key == candidates)
        module = modules(k);
        return;
    end
end
error('Unknown module reference: %s',string(moduleRef));
end
