function run_module_checks(moduleRef)
%RUN_MODULE_CHECKS Execute deterministic checks for one implemented module.
arguments
    moduleRef = "P01"
end
root = fileparts(mfilename('fullpath'));
manifest = jsondecode(fileread(fullfile(root,'curriculum','modules.json')));
module = resolveModule(manifest.modules,moduleRef);
folder = fullfile(root,module.folder);
checkFile = fullfile(folder,'run_checks.m');
if ~isfile(checkFile)
    error('%s has no run_checks.m.',module.id);
end
addpath(folder,'-begin');
cleanup = onCleanup(@() rmpath(folder)); %#ok<NASGU>
clear run_checks model;
run_checks();
end

function module = resolveModule(modules,moduleRef)
key=upper(string(moduleRef));
for k=1:numel(modules)
    if any(key == [upper(string(modules(k).id)), string(modules(k).number), ...
            sprintf('%02d',modules(k).number), upper(string(modules(k).slug))])
        module=modules(k); return;
    end
end
error('Unknown module reference: %s',string(moduleRef));
end
