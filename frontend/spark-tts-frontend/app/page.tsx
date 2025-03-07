"use client"

import type React from "react"

import { useState, useRef } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Slider } from "@/components/ui/slider"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Loader2, Upload, Play, Volume2 } from "lucide-react"

export default function Home() {
  const [loading, setLoading] = useState(false)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement>(null)

  // Voice Clone state
  const [cloneText, setCloneText] = useState("")
  const [promptText, setPromptText] = useState("")
  const [promptAudio, setPromptAudio] = useState<File | null>(null)
  const [clonePitch, setClonePitch] = useState(3)
  const [cloneSpeed, setCloneSpeed] = useState(3)

  // Voice Create state
  const [createText, setCreateText] = useState("")
  const [gender, setGender] = useState("male")
  const [createPitch, setCreatePitch] = useState(3)
  const [createSpeed, setCreateSpeed] = useState(3)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setPromptAudio(e.target.files[0])
    }
  }

  const handleVoiceClone = async () => {
    if (!cloneText) return

    setLoading(true)
    setAudioUrl(null)

    try {
      const formData = new FormData()
      formData.append("text", cloneText)
      formData.append("pitch", clonePitch.toString())
      formData.append("speed", cloneSpeed.toString())
      formData.append("stream", "true")

      if (promptText) {
        formData.append("prompt_text", promptText)
      }

      if (promptAudio) {
        formData.append("prompt_audio", promptAudio)
      }

      const response = await fetch("http://localhost:8000/voice_clone", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        throw new Error("Failed to generate audio")
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      setAudioUrl(url)

      if (audioRef.current) {
        audioRef.current.src = url
        audioRef.current.play()
      }
    } catch (error) {
      console.error("Error generating audio:", error)
    } finally {
      setLoading(false)
    }
  }

  const handleVoiceCreate = async () => {
    if (!createText) return

    setLoading(true)
    setAudioUrl(null)

    try {
      const formData = new FormData()
      formData.append("text", createText)
      formData.append("gender", gender)
      formData.append("pitch", createPitch.toString())
      formData.append("speed", createSpeed.toString())
      formData.append("stream", "true")

      const response = await fetch("http://localhost:8000/voice_create", {
        method: "POST",
        body: formData,
      })

      if (!response.ok) {
        throw new Error("Failed to generate audio")
      }

      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      setAudioUrl(url)

      if (audioRef.current) {
        audioRef.current.src = url
        audioRef.current.play()
      }
    } catch (error) {
      console.error("Error generating audio:", error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container mx-auto py-8 px-4">
      <h1 className="text-3xl font-bold mb-6 text-center">Spark TTS Voice Generator</h1>

      <Tabs defaultValue="clone" className="max-w-3xl mx-auto">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="clone">Voice Cloning</TabsTrigger>
          <TabsTrigger value="create">Voice Creation</TabsTrigger>
        </TabsList>

        <TabsContent value="clone" className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="clone-text">Text to Convert</Label>
              <Textarea
                id="clone-text"
                placeholder="Enter text to convert to speech..."
                value={cloneText}
                onChange={(e) => setCloneText(e.target.value)}
                className="h-32"
              />
            </div>

            <div>
              <Label htmlFor="prompt-text">Prompt Text (Optional)</Label>
              <Input
                id="prompt-text"
                placeholder="Enter prompt text..."
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
              />
            </div>

            <div>
              <Label htmlFor="prompt-audio">Voice Sample</Label>
              <div className="flex items-center gap-4 mt-1">
                <Button
                  variant="outline"
                  onClick={() => document.getElementById("prompt-audio")?.click()}
                  className="w-full"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  {promptAudio ? promptAudio.name : "Upload Audio Sample"}
                </Button>
                <Input
                  id="prompt-audio"
                  type="file"
                  accept=".wav,.mp3,.m4a"
                  onChange={handleFileChange}
                  className="hidden"
                />
              </div>
            </div>

            <div>
              <Label>Pitch (1-5)</Label>
              <Slider
                value={[clonePitch]}
                min={1}
                max={5}
                step={1}
                onValueChange={(value) => setClonePitch(value[0])}
                className="my-2"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Lower</span>
                <span>Default</span>
                <span>Higher</span>
              </div>
            </div>

            <div>
              <Label>Speed (1-5)</Label>
              <Slider
                value={[cloneSpeed]}
                min={1}
                max={5}
                step={1}
                onValueChange={(value) => setCloneSpeed(value[0])}
                className="my-2"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Slower</span>
                <span>Default</span>
                <span>Faster</span>
              </div>
            </div>

            <Button onClick={handleVoiceClone} disabled={loading || !cloneText} className="w-full">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Generate Audio
                </>
              )}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="create" className="space-y-6">
          <div className="space-y-4">
            <div>
              <Label htmlFor="create-text">Text to Convert</Label>
              <Textarea
                id="create-text"
                placeholder="Enter text to convert to speech..."
                value={createText}
                onChange={(e) => setCreateText(e.target.value)}
                className="h-32"
              />
            </div>

            <div>
              <Label>Voice Gender</Label>
              <RadioGroup value={gender} onValueChange={setGender} className="flex space-x-4 mt-1">
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="male" id="male" />
                  <Label htmlFor="male">Male</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <RadioGroupItem value="female" id="female" />
                  <Label htmlFor="female">Female</Label>
                </div>
              </RadioGroup>
            </div>

            <div>
              <Label>Pitch (1-5)</Label>
              <Slider
                value={[createPitch]}
                min={1}
                max={5}
                step={1}
                onValueChange={(value) => setCreatePitch(value[0])}
                className="my-2"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Lower</span>
                <span>Default</span>
                <span>Higher</span>
              </div>
            </div>

            <div>
              <Label>Speed (1-5)</Label>
              <Slider
                value={[createSpeed]}
                min={1}
                max={5}
                step={1}
                onValueChange={(value) => setCreateSpeed(value[0])}
                className="my-2"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Slower</span>
                <span>Default</span>
                <span>Faster</span>
              </div>
            </div>

            <Button onClick={handleVoiceCreate} disabled={loading || !createText} className="w-full">
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Generate Audio
                </>
              )}
            </Button>
          </div>
        </TabsContent>
      </Tabs>

      {audioUrl && (
        <div className="mt-8 max-w-3xl mx-auto p-4 border rounded-lg bg-muted/30">
          <h2 className="text-lg font-medium flex items-center mb-3">
            <Volume2 className="mr-2 h-5 w-5" />
            Generated Audio
          </h2>
          <audio ref={audioRef} controls className="w-full" src={audioUrl}>
            Your browser does not support the audio element.
          </audio>
        </div>
      )}
    </main>
  )
}

