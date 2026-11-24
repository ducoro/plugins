import AVFoundation
import CoreMedia
import Foundation
import ImageIO

struct PackResult: Encodable {
    let assetId: String
    let pvtPath: String
    let jpgPath: String
    let movPath: String
    let metadataPlist: String
}

func fail(_ msg: String, code: Int32 = 1) -> Never {
    fputs("ERROR: \(msg)\n", stderr)
    exit(code)
}

guard CommandLine.arguments.count == 4 || CommandLine.arguments.count == 5 else {
    fail("Usage: swift live_photo_packager.swift <input.jpg> <input.mov> <output.pvt> [asset-uuid]", code: 2)
}

let fm = FileManager.default
let inputJpg = URL(fileURLWithPath: CommandLine.arguments[1]).standardizedFileURL
let inputMov = URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL
let outputPvt = URL(fileURLWithPath: CommandLine.arguments[3]).standardizedFileURL
let assetId = (CommandLine.arguments.count == 5 && !CommandLine.arguments[4].isEmpty)
    ? CommandLine.arguments[4].uppercased()
    : UUID().uuidString.uppercased()

guard fm.fileExists(atPath: inputJpg.path) else { fail("Missing JPG: \(inputJpg.path)") }
guard fm.fileExists(atPath: inputMov.path) else { fail("Missing MOV: \(inputMov.path)") }

if fm.fileExists(atPath: outputPvt.path) {
    try fm.removeItem(at: outputPvt)
}
try fm.createDirectory(at: outputPvt, withIntermediateDirectories: true)

let outJpg = outputPvt.appendingPathComponent("IMG.JPG")
let outMov = outputPvt.appendingPathComponent("IMG.MOV")
let outPlist = outputPvt.appendingPathComponent("metadata.plist")

// 1. Write JPG with Apple MakerNote tag 17 = assetId
guard let src = CGImageSourceCreateWithURL(inputJpg as CFURL, nil),
      let imgType = CGImageSourceGetType(src) else {
    fail("Unable to read input JPG via ImageIO")
}
let imgCount = CGImageSourceGetCount(src)
guard let dst = CGImageDestinationCreateWithURL(outJpg as CFURL, imgType, imgCount, nil) else {
    fail("Unable to create output JPG destination")
}
for idx in 0..<imgCount {
    var props = (CGImageSourceCopyPropertiesAtIndex(src, idx, nil) as? [String: Any]) ?? [:]
    var appleMaker = (props[kCGImagePropertyMakerAppleDictionary as String] as? [String: Any]) ?? [:]
    appleMaker["17"] = assetId
    props[kCGImagePropertyMakerAppleDictionary as String] = appleMaker
    CGImageDestinationAddImageFromSource(dst, src, idx, props as CFDictionary)
}
guard CGImageDestinationFinalize(dst) else {
    fail("Failed to finalize Live Photo JPG")
}

// 2. Rewrite MOV with QuickTime content.identifier + timed still-image-time track
let asset = AVURLAsset(url: inputMov)
let sema = DispatchSemaphore(value: 0)
var movError: String?

Task {
    do {
        let videoTracks = try await asset.loadTracks(withMediaType: .video)
        guard let vTrack = videoTracks.first else {
            movError = "Input MOV contains no video track"
            sema.signal()
            return
        }
        let duration = try await asset.load(.duration)
        let naturalSize = try await vTrack.load(.naturalSize)
        let preferredTransform = try await vTrack.load(.preferredTransform)
        let nominalFps = try await vTrack.load(.nominalFrameRate)

        let reader = try AVAssetReader(asset: asset)
        let vReadOut = AVAssetReaderTrackOutput(track: vTrack, outputSettings: [
            kCVPixelBufferPixelFormatTypeKey as String: Int(kCVPixelFormatType_32BGRA)
        ])
        vReadOut.alwaysCopiesSampleData = false
        guard reader.canAdd(vReadOut) else {
            movError = "Cannot attach video reader output"
            sema.signal()
            return
        }
        reader.add(vReadOut)

        let audioTracks = try await asset.loadTracks(withMediaType: .audio)
        var aReadOut: AVAssetReaderTrackOutput?
        if let aTrack = audioTracks.first {
            let out = AVAssetReaderTrackOutput(track: aTrack, outputSettings: [
                AVFormatIDKey: kAudioFormatLinearPCM
            ])
            if reader.canAdd(out) {
                reader.add(out)
                aReadOut = out
            }
        }

        let writer = try AVAssetWriter(outputURL: outMov, fileType: .mov)
        let contentIdItem = AVMutableMetadataItem()
        contentIdItem.keySpace = .quickTimeMetadata
        contentIdItem.key = "com.apple.quicktime.content.identifier" as NSString
        contentIdItem.value = assetId as NSString
        contentIdItem.dataType = kCMMetadataBaseDataType_UTF8 as String
        writer.metadata = [contentIdItem]

        let width = Int(abs(naturalSize.width))
        let height = Int(abs(naturalSize.height))
        let vWriteIn = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width,
            AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: 6_000_000,
                AVVideoExpectedSourceFrameRateKey: nominalFps > 0 ? nominalFps : 30.0
            ]
        ])
        vWriteIn.expectsMediaDataInRealTime = false
        vWriteIn.transform = preferredTransform
        writer.add(vWriteIn)

        var aWriteIn: AVAssetWriterInput?
        if aReadOut != nil {
            let inp = AVAssetWriterInput(mediaType: .audio, outputSettings: [
                AVFormatIDKey: kAudioFormatMPEG4AAC,
                AVSampleRateKey: 44100,
                AVNumberOfChannelsKey: 2,
                AVEncoderBitRateKey: 128000
            ])
            inp.expectsMediaDataInRealTime = false
            if writer.canAdd(inp) {
                writer.add(inp)
                aWriteIn = inp
            }
        }

        // Timed metadata track for com.apple.quicktime.still-image-time
        let spec: [[String: Any]] = [[
            kCMMetadataFormatDescriptionMetadataSpecificationKey_Identifier as String: "mdta/com.apple.quicktime.still-image-time",
            kCMMetadataFormatDescriptionMetadataSpecificationKey_DataType as String: kCMMetadataBaseDataType_SInt8 as String
        ]]
        var desc: CMFormatDescription?
        CMMetadataFormatDescriptionCreateWithMetadataSpecifications(
            allocator: kCFAllocatorDefault,
            metadataType: kCMMetadataFormatType_Boxed,
            metadataSpecifications: spec as CFArray,
            formatDescriptionOut: &desc
        )
        let metaInput = AVAssetWriterInput(mediaType: .metadata, outputSettings: nil, sourceFormatHint: desc)
        let metaAdaptor = AVAssetWriterInputMetadataAdaptor(assetWriterInput: metaInput)
        writer.add(metaInput)

        guard writer.startWriting(), reader.startReading() else {
            movError = "Failed to start AVAssetReader/AVAssetWriter: \(writer.error?.localizedDescription ?? reader.error?.localizedDescription ?? "unknown")"
            sema.signal()
            return
        }
        writer.startSession(atSourceTime: .zero)

        let stillItem = AVMutableMetadataItem()
        stillItem.keySpace = .quickTimeMetadata
        stillItem.key = "com.apple.quicktime.still-image-time" as NSString
        stillItem.value = NSNumber(value: 0)
        stillItem.dataType = kCMMetadataBaseDataType_SInt8 as String
        let stillRange = CMTimeRange(start: .zero, duration: CMTime(value: 1, timescale: 600))
        metaAdaptor.append(AVTimedMetadataGroup(items: [stillItem], timeRange: stillRange))
        metaInput.markAsFinished()

        let pumpGroup = DispatchGroup()
        let videoQueue = DispatchQueue(label: "ducoro.livephoto.video")
        pumpGroup.enter()
        vWriteIn.requestMediaDataWhenReady(on: videoQueue) {
            while vWriteIn.isReadyForMoreMediaData {
                if let sample = vReadOut.copyNextSampleBuffer() {
                    if !vWriteIn.append(sample) {
                        vWriteIn.markAsFinished()
                        pumpGroup.leave()
                        return
                    }
                } else {
                    vWriteIn.markAsFinished()
                    pumpGroup.leave()
                    return
                }
            }
        }

        if let aOut = aReadOut, let aIn = aWriteIn {
            let audioQueue = DispatchQueue(label: "ducoro.livephoto.audio")
            pumpGroup.enter()
            aIn.requestMediaDataWhenReady(on: audioQueue) {
                while aIn.isReadyForMoreMediaData {
                    if let sample = aOut.copyNextSampleBuffer() {
                        if !aIn.append(sample) {
                            aIn.markAsFinished()
                            pumpGroup.leave()
                            return
                        }
                    } else {
                        aIn.markAsFinished()
                        pumpGroup.leave()
                        return
                    }
                }
            }
        }

        pumpGroup.wait()
        await writer.finishWriting()
        if writer.status != .completed {
            movError = "Writer failed: \(writer.error?.localizedDescription ?? "unknown") (duration=\(duration.seconds))"
        }
    } catch {
        movError = error.localizedDescription
    }
    sema.signal()
}

sema.wait()
if let err = movError {
    fail(err)
}

// 3. Write Apple .pvt metadata.plist
let plistDict: [String: Any] = [
    "PFVideoComplementMetadataVersionKey": "1",
    "PFVideoComplementMetadataPairingIdentifierKey": assetId
]
let plistData = try PropertyListSerialization.data(fromPropertyList: plistDict, format: .xml, options: 0)
try plistData.write(to: outPlist)

let result = PackResult(
    assetId: assetId,
    pvtPath: outputPvt.path,
    jpgPath: outJpg.path,
    movPath: outMov.path,
    metadataPlist: outPlist.path
)
let json = try JSONEncoder().encode(result)
if let str = String(data: json, encoding: .utf8) {
    print(str)
}
