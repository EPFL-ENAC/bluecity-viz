<template>
  <div class="pb-8">
    <div class="slider-container">
      <v-btn class="play-button" density="compact" flat @click="togglePlay">{{
        playing ? 'Pause' : 'Play'
      }}</v-btn>
    </div>
    <div id="slider-round" ref="sliderHTML" class="slider-styled" />
  </div>
</template>

<script setup lang="ts">
import noUiSlider, { PipsMode, type API } from 'nouislider'
import 'nouislider/dist/nouislider.css'

import { defineModel, onUnmounted, onMounted, ref } from 'vue'

const timecodes = [
  '2022-06-01_00:00:00',
  '2022-06-02_00:00:00',
  '2022-06-03_00:00:00',
  '2022-06-03_06:00:00',
  '2022-06-04_00:00:00',
  '2022-06-04_06:00:00',
  '2022-06-04_12:00:00',
  '2022-06-05_00:00:00',
  '2022-06-05_12:00:00',
  '2022-06-06_00:00:00',
  '2022-06-06_12:00:00',
  '2022-06-07_00:00:00',
  '2022-06-07_12:00:00',
  '2022-06-08_00:00:00',
  '2022-06-08_12:00:00',
  '2022-06-09_00:00:00',
  '2022-06-09_12:00:00',
  '2022-06-10_00:00:00',
  '2022-06-10_12:00:00',
  '2022-06-11_00:00:00',
  '2022-06-11_12:00:00',
  '2022-06-12_00:00:00',
  '2022-06-12_12:00:00',
  '2022-06-13_00:00:00',
  '2022-06-13_12:00:00',
  '2022-06-14_00:00:00',
  '2022-06-15_00:00:00',
  '2022-06-16_00:00:00',
  '2022-06-17_00:00:00',
  '2022-06-18_00:00:00',
  '2022-06-19_00:00:00',
  '2022-06-20_00:00:00',
  '2022-06-21_00:00:00',
  '2022-06-22_00:00:00',
  '2022-06-23_00:00:00',
  '2022-06-24_00:00:00',
  '2022-06-25_00:00:00',
  '2022-06-26_00:00:00',
  '2022-06-27_00:00:00',
  '2022-06-28_00:00:00',
  '2022-06-29_00:00:00',
  '2022-06-30_00:00:00'
].map((dateString) => {
  const formattedString = dateString.replace(/_/g, ' ')
  const dateObject = new Date(formattedString)
  return dateObject.getTime()
})

const sliderHTML = ref<HTMLDivElement | null>(null)
const slider = ref<API | null>(null)
const playing = ref(false)
const modelValue = defineModel<number>({ required: true })

let playInterval: any

const formatDate = {
  to: (value: number) => {
    const date = new Date(timecodes[Math.round(value)])
    return date.toLocaleString('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: '2-digit'
    }) // hh:mm dd/mm/yy
  },
  from: (value: string) => {
    const [datePart, timePart] = value.split(' ')
    const [day, month, year] = datePart.split('/').map(Number)
    const [hours, minutes] = timePart.split(':').map(Number)
    const date = new Date(2000 + year, month - 1, day, hours, minutes)
    return timecodes.indexOf(date.getTime())
  }
}

const formatDateSimple = {
  to: (value: number) => {
    const date = new Date(timecodes[Math.round(value)])
    return date.toLocaleDateString('en-GB', {
      day: '2-digit',
      month: '2-digit'
    }) // dd/mm
  },
  from: (value: string) => {
    const [day, month] = value.split('/').map(Number)
    const today = new Date()
    const year = today.getFullYear() // Assuming current year for simplicity
    const date = new Date(year, month - 1, day)
    return timecodes.indexOf(date.getTime())
  }
}

const formatNumber = {
  to: (value: number) => {
    return Math.round(value)
  },
  from: (value: string) => {
    return Number(value)
  }
}

const createSlider = () => {
  if (!sliderHTML.value) return
  slider.value = noUiSlider.create(sliderHTML.value, {
    start: modelValue.value,
    tooltips: [formatDate],
    format: formatNumber,
    range: {
      min: 0,
      max: timecodes.length - 1
    },
    step: 1,
    pips: {
      mode: PipsMode.Steps,
      filter: (value: number) => {
        return value % 5 === 0 ? 1 : 0
      },
      format: formatDateSimple
    }
  })

  slider.value.on('update', (value) => {
    if (Number(value)) modelValue.value = Number(value) as number
  })
}

const play = () => {
  if (playing.value) return
  playing.value = true

  playInterval = setInterval(() => {
    if (slider.value) slider.value.set(modelValue.value + 1)
  }, 800)
}

const stop = () => {
  playing.value = false
  clearInterval(playInterval)
}

const togglePlay = () => {
  playing.value ? stop() : play()
}

onMounted(createSlider)
onUnmounted(stop)
</script>

<style scoped>
.slider-container {
  position: relative;
  z-index: 100;
  padding-top: 25px;
}

.play-button {
  position: absolute;
  top: -35px;
  right: 0;
}

.slider-styled {
  width: 100%;
  height: 10px;
  padding: 0 0;
}

:deep().noUi-connect {
  background: #c0392b;
}

:deep().noUi-handle {
  height: 18px;
  width: 18px;
  top: -5px;
  right: -9px; /* half the width */
  border-radius: 9px;
}

:deep().noUi-handle:before,
:deep().noUi-handle:after {
  display: none;
}

:deep().noUi-pips {
  padding: 2px;
}
:deep().noUi-touch-area {
  padding: 15px;
  /* transform: translate(-50%, -50%); */
  cursor: move;
}

:deep().noUi-marker-horizontal {
  /* padding: 0px; */
}

:deep().noUi-value {
  padding-top: 4px;
}
</style>
