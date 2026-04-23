<template>
  <q-banner
    v-if="updateAvailable"
    inline-actions
    dense
    class="version-update-banner bg-primary text-white"
  >
    <template #avatar>
      <q-icon name="system_update_alt" />
    </template>
    Доступна новая версия CRM. Пожалуйста, обновите страницу, чтобы продолжить работу.
    <template #action>
      <q-btn flat no-caps label="Обновить" icon="refresh" @click="reload" />
    </template>
  </q-banner>
  <router-view />
</template>

<script setup>
import { useVersionCheck } from 'src/composables/useVersionCheck'

const { updateAvailable, reload } = useVersionCheck()
</script>

<style scoped>
.version-update-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}
</style>
