<template>
    <div class="col column">
        <q-bar class="bg-primary text-white text-weight-bold">Environment Overrides&nbsp;<q-icon name="info"><q-tooltip>The environment overrides are saved on the server when the stack is started.<br />Until that point, your overrides are only stored temporarily in your browser.</q-tooltip></q-icon>
            <q-space />
            <q-btn dense flat icon="save" :disable="!envOverrides?.trim()" @click="openSaveDialog()"><q-tooltip>Save overrides as preset</q-tooltip></q-btn>
            <q-btn dense flat icon="folder_open" @click="presetsDialogActive = true"><q-tooltip>Load a saved preset</q-tooltip></q-btn>
        </q-bar>
        <q-card flat bordered square class="column col q-pa-sm env-overrides-textarea" style="min-height: 100px;">
            <q-input v-model="envOverrides" filled square type="textarea" class="column col" style="white-space: pre; font-family: monospace;" dense input-class="col full-height" input-style="" />
            <q-btn label="Reload from server" icon="update" class="bg-primary text-white" @click="reload()" />
        </q-card>
        <EnvPresetsDialog v-model="presetsDialogActive" :stack-name="stackName" :current-overrides="envOverrides" @load="onPresetLoad" />
        <q-dialog v-model="saveDialogActive">
            <q-card style="width: 500px; max-width: 90vw;">
                <q-card-section><div class="text-h6">Save Environment Preset</div><div class="text-caption">for stack <b>{{ stackName }}</b></div></q-card-section>
                <q-card-section>
                    <q-input v-model="savePresetName" autofocus dense outlined label="Preset Name" style="font-family: monospace;" :rules="[val => presetNameValid || 'Use 1-64 characters: letters, digits, _, - and .']" @keyup.enter="savePreset()" />
                    <div v-if="presetExists" class="text-negative text-caption">A preset with this name already exists and will be overwritten.</div>
                </q-card-section>
                <q-card-actions align="right">
                    <q-btn flat label="Cancel" icon="close" @click="saveDialogActive = false" />
                    <q-btn :color="presetExists ? 'negative' : 'positive'" :label="presetExists ? 'Overwrite' : 'Save'" icon="save" :disable="!presetNameValid" :loading="saving || checkingExisting" @click="savePreset()" />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<script>
import { storeToRefs } from 'pinia';
import { useStackStore } from 'src/stores/stacks';
import { Notify } from 'quasar';
import { ref, computed, onMounted, watch } from 'vue';
import EnvPresetsDialog from './EnvPresetsDialog.vue';

const PRESET_NAME_REGEX = /^[A-Za-z0-9._-]{1,64}$/;

export default {
    components: { EnvPresetsDialog },
    props: {
        stackName: { type: String, required: true }
    },

    async setup(props) {
        const stackStore = useStackStore();
        const envOverrides = ref('');

        async function ensureStackIsInStore() {
            const result = await stackStore.ensureStackIsInStore(props.stackName)
            if(!result) return {};
        }

        async function loadData() {
            await ensureStackIsInStore();

            if(storeToRefs(stackStore).stacks.value[props.stackName].envOverrides === null)
                await stackStore.loadStackEnvOverrides(props.stackName);
            envOverrides.value = storeToRefs(stackStore).stacks.value[props.stackName].envOverrides;
        }

        async function saveData() {
            await ensureStackIsInStore();

            storeToRefs(stackStore).stacks.value[props.stackName].envOverrides = envOverrides.value;
        }

        async function reload() {
            await ensureStackIsInStore();

            storeToRefs(stackStore).stacks.value[props.stackName].envOverrides = null;
            await loadData();
        }

        onMounted(() => loadData());

        watch(
            () => props.stackName,
            () => loadData()
        );

        watch(envOverrides, () => saveData());

        const presetsDialogActive = ref(false);
        const saveDialogActive = ref(false);
        const savePresetName = ref('');
        const saving = ref(false);
        // Saving waits for the reloaded preset list, so an existing preset is never overwritten without the warning
        const checkingExisting = ref(false);
        // Name of the last loaded or saved preset, used to prefill the save dialog
        const lastPresetName = ref('');

        watch(() => props.stackName, () => { lastPresetName.value = ''; });

        const presetNameValid = computed(() => PRESET_NAME_REGEX.test(savePresetName.value) && !['.', '..'].includes(savePresetName.value));
        const presetExists = computed(() => {
            const stack = (stackStore.envPresets || []).find(s => s.stack_name === props.stackName);
            return !!stack && stack.presets.includes(savePresetName.value);
        });

        function openSaveDialog() {
            savePresetName.value = lastPresetName.value;
            saveDialogActive.value = true;
            checkingExisting.value = true;
            stackStore.loadEnvPresets().finally(() => { checkingExisting.value = false; });
        }

        async function savePreset() {
            if(!presetNameValid.value || saving.value || checkingExisting.value) return;
            saving.value = true;
            const name = savePresetName.value;
            if(await stackStore.saveEnvPreset(props.stackName, name, envOverrides.value)) {
                lastPresetName.value = name;
                saveDialogActive.value = false;
                Notify.create({ message: `Saved preset ${name} for stack ${props.stackName}.`, color: 'positive', icon: 'save' });
            }
            saving.value = false;
        }

        function onPresetLoad({ content, stack, preset }) {
            envOverrides.value = content;
            lastPresetName.value = preset;
            Notify.create({ message: `Loaded preset ${preset}${stack !== props.stackName ? ' of stack ' + stack : ''}.`, color: 'positive', icon: 'file_open' });
        }

        return {
            stackStore, envOverrides, reload,
            presetsDialogActive, saveDialogActive, savePresetName, saving, checkingExisting,
            presetNameValid, presetExists, openSaveDialog, savePreset, onPresetLoad
        };
    }
}
</script>
<style lang="sass">
.env-overrides-textarea
  /* height or max-height is important */

  .q-filed__inner,
  .q-field__control,
  .q-field__control-container
    height: 100%
</style>
