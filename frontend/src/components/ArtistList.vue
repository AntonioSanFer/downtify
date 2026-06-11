<template>
  <div
    v-if="sm.isSearchingArtists.value || artists.length"
    class="mx-auto max-w-4xl px-4 pt-8 sm:px-6"
  >
    <h2
      class="text-sm font-semibold uppercase tracking-wider text-base-content/50 mb-3"
    >
      {{ t('artist.title') }}
    </h2>

    <!-- Loading skeleton -->
    <div v-if="sm.isSearchingArtists.value" class="space-y-2">
      <div class="skeleton h-20 rounded-2xl" />
    </div>

    <ul v-else class="space-y-2">
      <li
        v-for="artist in artists.slice(0, shown)"
        :key="artist.artist_id"
        class="surface rounded-2xl track-card"
      >
        <!-- Cover -->
        <div class="track-cover !rounded-full overflow-hidden">
          <img
            v-if="artist.cover_url"
            :src="artist.cover_url"
            :alt="artist.name"
            class="h-full w-full object-cover"
            loading="lazy"
          />
          <div
            v-else
            class="h-full w-full flex items-center justify-center text-base-content/30"
          >
            <Icon icon="clarity:user-line" class="h-6 w-6" />
          </div>
        </div>

        <!-- Info -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="font-semibold truncate">{{ artist.name }}</span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-1 shrink-0">
          <a
            v-if="artist.url"
            class="icon-btn"
            :href="artist.url"
            target="_blank"
            rel="noopener"
            :title="t('search.openOnSpotify')"
          >
            <Icon icon="clarity:pop-out-line" class="h-4 w-4" />
          </a>

          <!-- Watch artist -->
          <button
            class="icon-btn"
            :class="
              watchState[artist.artist_id] === 'watched'
                ? 'text-primary cursor-default'
                : 'hover:bg-primary/10'
            "
            :disabled="watchState[artist.artist_id] === 'adding'"
            :title="
              watchState[artist.artist_id] === 'watched'
                ? t('artist.watching')
                : t('artist.watch')
            "
            @click="watch(artist)"
          >
            <span
              v-if="watchState[artist.artist_id] === 'adding'"
              class="loading loading-spinner loading-xs"
            />
            <Icon
              v-else-if="watchState[artist.artist_id] === 'watched'"
              icon="clarity:eye-show-line"
              class="h-5 w-5"
            />
            <Icon v-else icon="clarity:eye-line" class="h-5 w-5" />
          </button>

          <!-- Download discography -->
          <button
            class="icon-btn text-primary hover:bg-primary/10"
            :disabled="downloading[artist.artist_id]"
            :title="t('artist.downloadAll')"
            @click="downloadAll(artist)"
          >
            <span
              v-if="downloading[artist.artist_id]"
              class="loading loading-spinner loading-xs"
            />
            <Icon v-else icon="clarity:download-line" class="h-5 w-5" />
          </button>
        </div>
      </li>
    </ul>

    <button
      v-if="!sm.isSearchingArtists.value && artists.length > shown"
      class="mt-2 text-xs text-primary hover:underline"
      @click="shown += 5"
    >
      {{ t('artist.showMore') }}
    </button>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { Icon } from '@iconify/vue'

import router from '../router'
import { useSearchManager } from '../model/search'
import { useDownloadManager } from '../model/download'
import monitorAPI from '../model/monitor'
import { useI18n } from '../i18n'

const sm = useSearchManager()
const dm = useDownloadManager()
const { t } = useI18n()

const shown = ref(3)
const watchState = ref({})
const downloading = ref({})

const artists = computed(() => sm.artistResults.value || [])

async function downloadAll(artist) {
  downloading.value = { ...downloading.value, [artist.artist_id]: true }
  try {
    await dm.fromURL(artist.url)
    router.push({ name: 'Download' })
  } finally {
    downloading.value = { ...downloading.value, [artist.artist_id]: false }
  }
}

async function watch(artist) {
  if (watchState.value[artist.artist_id] === 'watched') {
    router.push({ name: 'Monitor' })
    return
  }
  watchState.value = { ...watchState.value, [artist.artist_id]: 'adding' }
  try {
    await monitorAPI.addMonitoredArtist(artist.url)
    watchState.value = { ...watchState.value, [artist.artist_id]: 'watched' }
  } catch (e) {
    // 409 — already monitored: treat as watched
    if (e?.response?.status === 409) {
      watchState.value = {
        ...watchState.value,
        [artist.artist_id]: 'watched',
      }
    } else {
      watchState.value = { ...watchState.value, [artist.artist_id]: 'idle' }
    }
  }
}
</script>
