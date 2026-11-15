// Native, offscreen GPU draw. This verifies Metal access, not Gazebo integration.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <cstdio>

int main() {
  @autoreleasepool {
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    if (!device) {
      std::fprintf(stderr, "FAIL: no native Metal device\n");
      return 1;
    }
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
      "vertex float4 vertexMain(uint id [[vertex_id]]) {"
      " float2 positions[3] = {float2(-1,-1),float2(3,-1),float2(-1,3)};"
      " return float4(positions[id],0,1); }"
      "fragment float4 fragmentMain() { return float4(0.25,0.5,0.75,1); }";
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    if (!library) {
      std::fprintf(stderr, "FAIL: shader compile: %s\n", error.description.UTF8String);
      return 1;
    }
    MTLRenderPipelineDescriptor *pipeline = [MTLRenderPipelineDescriptor new];
    pipeline.vertexFunction = [library newFunctionWithName:@"vertexMain"];
    pipeline.fragmentFunction = [library newFunctionWithName:@"fragmentMain"];
    pipeline.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    id<MTLRenderPipelineState> state = [device newRenderPipelineStateWithDescriptor:pipeline error:&error];
    if (!state) {
      std::fprintf(stderr, "FAIL: render pipeline: %s\n", error.description.UTF8String);
      return 1;
    }
    MTLTextureDescriptor *description = [MTLTextureDescriptor
      texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];
    description.usage = MTLTextureUsageRenderTarget;
    description.storageMode = MTLStorageModeShared;
    id<MTLTexture> texture = [device newTextureWithDescriptor:description];
    id<MTLCommandQueue> queue = [device newCommandQueue];
    id<MTLCommandBuffer> command = [queue commandBuffer];
    if (!texture || !queue || !command) {
      std::fprintf(stderr, "FAIL: Metal resource allocation\n");
      return 1;
    }
    MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor new];
    pass.colorAttachments[0].texture = texture;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
    [encoder setRenderPipelineState:state];
    [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [encoder endEncoding];
    [command commit];
    [command waitUntilCompleted];
    if (command.status != MTLCommandBufferStatusCompleted) {
      std::fprintf(stderr, "FAIL: GPU command: %s\n", command.error.description.UTF8String);
      return 1;
    }
    unsigned char pixels[16 * 16 * 4] = {};
    [texture getBytes:pixels bytesPerRow:16 * 4 fromRegion:MTLRegionMake2D(0,0,16,16) mipmapLevel:0];
    for (unsigned i = 0; i < sizeof(pixels); i += 4) {
      if (pixels[i] < 62 || pixels[i] > 65 || pixels[i+1] < 126 || pixels[i+1] > 129
          || pixels[i+2] < 190 || pixels[i+2] > 193 || pixels[i+3] != 255) {
        std::fprintf(stderr, "FAIL: GPU pixel readback differs from fragment shader\n");
        return 1;
      }
    }
    std::printf("PASS: Metal device: %s; GPU draw and pixel readback verified\n", device.name.UTF8String);
    return 0;
  }
}
