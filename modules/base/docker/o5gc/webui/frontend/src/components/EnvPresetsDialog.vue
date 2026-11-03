<template>
    <q-dialog :model-value="modelValue" @update:model-value="val => $emit('update:modelValue', val)" @before-show="onBeforeShow">
        <q-card style="width: 1100px; max-width: 90vw;">
            <q-bar class="bg-primary text-white text-weight-bold">
                Environment Presets
                <q-space />
                <q-btn v-close-popup dense flat icon="close"><q-tooltip>Close</q-tooltip></q-btn>
            </q-bar>
            <q-card-section class="row q-col-gutter-sm">
                <div class="col-md-5 col-xs-12 column">
                    <q-input v-model="filter" filled dense label="Filter" class="col-auto">
                        <template #append>
                            <q-icon v-if="filter !== ''" name="clear" class="cursor-pointer" @click="filter = ''" />
                        </template>
                    </q-input>
                    <q-scroll-area class="env-presets-pane">
                        <q-tree ref="treeRef" v-model:selected="selected" v-model:expanded="expanded" :nodes="nodes" node-key="key" :filter="filter" :filter-method="filterMethod" no-selection-unset dense>
                            <template #header-module="prop">
                                <q-icon name="folder" class="q-mr-sm" />{{ prop.node.label }}
                            </template>
                            <template #header-stack="prop">
                                <span :class="{ 'text-grey-6': prop.node.children.length === 0, 'text-weight-bold': prop.node.label === stackName }">{{ prop.node.label }}</span>
                                <q-badge v-if="prop.node.label === stackName" color="primary" class="q-ml-sm">current</q-badge>
                            </template>
                            <template #header-preset="prop">
                                <q-icon name="description" class="q-mr-sm" />{{ prop.node.label }}
                            </template>
                        </q-tree>
                    </q-scroll-area>
                </div>
                <div class="col-md-7 col-xs-12">
                    <div v-if="selectedPreset" class="text-caption q-mb-xs">{{ selectedPreset.module }} / {{ selectedPreset.stack }} / <b>{{ selectedPreset.preset }}</b></div>
                    <div v-else class="text-caption q-mb-xs text-italic">Select a preset to preview it.</div>
                    <q-scroll-area class="env-presets-pane env-presets-preview">
                        <q-inner-loading :showing="previewLoading" />
                        <pre class="q-ma-none q-pa-sm" style="font-family: monospace;">{{ preview }}</pre>
                    </q-scroll-area>
                </div>
            </q-card-section>
            <q-card-actions align="right">
                <q-btn flat color="negative" icon="delete" label="Delete" :disable="!selectedPreset" @click="deleteConfirmActive = true" />
                <q-btn color="primary" icon="file_open" :label="`Load into ${stackName}`" :disable="!selectedPreset || preview === null || previewLoading" @click="requestLoad()" />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <q-dialog v-model="loadConfirmActive" persistent>
        <q-card>
            <q-card-section class="row items-center no-wrap">
                <q-avatar icon="warning" color="warning" text-color="black" />
                <span class="q-ml-sm">Replace the current environment overrides of <b>{{ stackName }}</b> with preset <b>{{ selectedPreset?.preset }}</b>?</span>
            </q-card-section>
            <q-card-actions align="right">
                <q-btn v-close-popup flat label="Replace" icon="check" color="positive" @click="load()" />
                <q-btn v-close-popup flat label="Cancel" icon="close" color="negative" />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <q-dialog v-model="deleteConfirmActive" persistent>
        <q-card>
            <q-card-section class="row items-center no-wrap">
                <q-avatar icon="warning" color="warning" text-color="black" />
                <span class="q-ml-sm">Delete preset <b>{{ selectedPreset?.preset }}</b> of stack <b>{{ selectedPreset?.stack }}</b>?</span>
            </q-card-section>
            <q-card-actions align="right">
                <q-btn v-close-popup flat label="Delete" icon="delete" color="negative" @click="deletePreset()" />
                <q-btn v-close-popup flat label="Cancel" icon="close" />
            </q-card-actions>
        </q-card>
    </q-dialog>
</template>

<script>
import { storeToRefs } from 'pinia';
import { useStackStore } from 'src/stores/stacks';
import { computed, nextTick, ref, watch } from 'vue';

export default {
    props: {
        modelValue: { type: Boolean, required: true },
        stackName: { type: String, required: true },
        currentOverrides: { type: String, default: '' }
    },
    emits: ['update:modelValue', 'load'],

    setup(props, { emit }) {
        const stackStore = useStackStore();
        const { envPresets, stacks } = storeToRefs(stackStore);

        const treeRef = ref(null);
        const filter = ref('');
        const selected = ref(null);
        const expanded = ref([]);
        const preview = ref(null);
        const previewLoading = ref(false);
        const loadConfirmActive = ref(false);
        const deleteConfirmActive = ref(false);

        const nodes = computed(() => {
            const modules = {};
            for(const s of envPresets.value || []) {
                // Stacks without presets are only shown for the current stack
                if(s.presets.length === 0 && s.stack_name !== props.stackName) continue;
                if(!(s.module_name in modules)) {
                    modules[s.module_name] = { key: `m:${s.module_name}`, label: s.module_name, header: 'module', selectable: false, children: [] };
                }
                modules[s.module_name].children.push({
                    key: `s:${s.stack_name}`, label: s.stack_name, header: 'stack', selectable: false,
                    children: s.presets.map(p => ({
                        key: `p:${s.stack_name}/${p}`, label: p, header: 'preset',
                        module: s.module_name, stack: s.stack_name, preset: p
                    }))
                });
            }
            return Object.values(modules);
        });

        const selectedPreset = computed(() => {
            if(!selected.value) return null;
            for(const m of nodes.value)
                for(const s of m.children)
                    for(const p of s.children)
                        if(p.key === selected.value) return p;
            return null;
        });

        // Matching a stack or module also shows all of its presets
        function filterMethod(node, filterText) {
            const needle = filterText.toLowerCase();
            const haystack = node.header === 'preset' ? [node.module, node.stack, node.preset] : [node.label];
            return haystack.some(h => h.toLowerCase().includes(needle));
        }

        // Reset before the dialog becomes visible, so the state of a previously shown stack never flashes up
        function onBeforeShow() {
            filter.value = '';
            selected.value = null;
            preview.value = null;
            const moduleName = stacks.value[props.stackName]?.module;
            expanded.value = moduleName ? [`m:${moduleName}`, `s:${props.stackName}`] : [];
            stackStore.loadEnvPresets();
        }

        watch(filter, (val) => {
            if(val) nextTick(() => treeRef.value?.expandAll());
        });

        watch(selectedPreset, async (node) => {
            preview.value = null;
            if(!node) return;
            previewLoading.value = true;
            const content = await stackStore.getEnvPreset(node.stack, node.preset);
            // Ignore late responses for a preset that is not selected anymore
            if(selectedPreset.value === node) preview.value = content;
            previewLoading.value = false;
        });

        function requestLoad() {
            if((props.currentOverrides || '').trim() !== '' && props.currentOverrides !== preview.value)
                loadConfirmActive.value = true;
            else
                load();
        }

        function load() {
            emit('load', { content: preview.value, ...selectedPreset.value });
            emit('update:modelValue', false);
        }

        async function deletePreset() {
            const node = selectedPreset.value;
            if(!node) return;
            if(await stackStore.deleteEnvPreset(node.stack, node.preset))
                selected.value = null;
        }

        return {
            treeRef, filter, selected, expanded, nodes, selectedPreset, preview, previewLoading,
            loadConfirmActive, deleteConfirmActive,
            filterMethod, onBeforeShow, requestLoad, load, deletePreset
        };
    }
}
</script>

<style lang="sass">
.env-presets-pane
  height: 55vh

.env-presets-preview
  border: 1px solid rgba(128, 128, 128, 0.4)

@media (max-width: 1023px)
  .env-presets-pane
    height: 30vh
</style>
