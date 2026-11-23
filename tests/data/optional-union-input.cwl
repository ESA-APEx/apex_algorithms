cwlVersion: v1.2
class: CommandLineTool
baseCommand: echo
inputs:
  message:
    type: string
    doc: "A required string message"
    inputBinding:
      position: 1
  optional_label:
    type: ["null", "string"]
    doc: "An optional label"
    inputBinding:
      position: 2
outputs: [ ]
