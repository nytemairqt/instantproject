#--------------------------------------------------------------
# Meta Dictionary
#--------------------------------------------------------------

bl_info = {
	'name' : 'InstantProject',
	'author' : 'SceneFiller',
	'version' : (1, 0, 6),
	'blender' : (3, 3, 0),
	'location' : 'View3d > Tool',
	'warning' : '',
	'wiki_url' : '',
	'category' : '3D View',
}

#--------------------------------------------------------------
# Import
#--------------------------------------------------------------

import os
import bpy
import bpy_extras
#from bpy.props import PointerProperty, BoolProperty
import math 
from mathutils import Vector
#import mathutils
from bpy_extras.image_utils import load_image
#from pathlib import Path
#import shutil
from bpy_extras import view3d_utils
from bpy_extras.io_utils import ImportHelper
#from PIL import Image

#--------------------------------------------------------------
# Miscellaneous Functions
#--------------------------------------------------------------

def INSTANTPROJECT_FN_setShaders(nodes, links, image_file):
	material_output = nodes.get('Material Output') # Output Node
	principled_bsdf = nodes.get('Principled BSDF') 
	nodes.remove(principled_bsdf) # Delete BSDF

	node_principled_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
	node_colorramp_roughness = nodes.new(type='ShaderNodeValToRGB')
	node_colorramp_specular = nodes.new(type='ShaderNodeValToRGB')
	node_bump = nodes.new(type='ShaderNodeBump')

	node_curves = nodes.new(type='ShaderNodeRGBCurve')
	node_HSV = nodes.new(type='ShaderNodeHueSaturation')
	node_albedo = nodes.new(type='ShaderNodeTexImage')

	node_curves.name = 'curves'
	node_HSV.name  = 'HSV'
	node_albedo.name = 'albedo'
	node_albedo.image = image_file

	# Connections
	link = links.new(node_HSV.outputs[0], node_principled_bsdf.inputs[0]) # HSV -> Principled BSDF
	link = links.new(node_albedo.outputs[0], node_curves.inputs[1]) # Albedo -> Curves
	link = links.new(node_curves.outputs[0], node_HSV.inputs[4]) # Curves -> HSV
	link = links.new(node_principled_bsdf.outputs[0], material_output.inputs[0]) # Principled BSDF -> Material Output
	link = links.new(node_HSV.outputs[0], node_colorramp_specular.inputs[0]) # HSV -> ColorRamp Specular
	link = links.new(node_colorramp_specular.outputs[0], node_principled_bsdf.inputs[7]) # ColorRamp Specular -> Color (Specular)
	link = links.new(node_HSV.outputs[0], node_colorramp_roughness.inputs[0]) # HSV -> ColorRamp Roughness	
	link = links.new(node_colorramp_roughness.outputs[0], node_principled_bsdf.inputs[9]) # ColorRamp Specular -> Color (Roughness)
	link = links.new(node_HSV.outputs[0], node_bump.inputs[2]) # HSV -> Bump
	link = links.new(node_bump.outputs[0], node_principled_bsdf.inputs[22]) # Bump -> Color (Bump)

	# Default Values

	node_bump.inputs[0].default_value = 0.2

	# Node Positions
	material_output.location = Vector((300.0, 0.0))
	node_principled_bsdf.location = Vector((-100.0, -200.0))
	node_albedo.location = Vector((-1500.0, -300.0))
	node_HSV.location = Vector((-800.0, -300.0))
	node_curves.location = Vector((-1100.0, -300.0))	
	node_colorramp_specular.location = Vector((-500,-300))
	node_colorramp_roughness.location = Vector((-500,-600))
	node_bump.location = Vector((-500,-900))

def INSTANTPROJECT_FN_contextOverride(area_to_check):
	return [area for area in bpy.context.screen.areas if area.type == area_to_check][0]

def INSTANTPROJECT_FN_removeDecalLayer(self, context):
	active_object = bpy.context.active_object
	if not active_object:
		self.report({'WARNING'}, 'No active object selected.')
		return{'CANCELLED'}
	nodes = active_object.data.materials[0].node_tree.nodes 
	links = active_object.data.materials[0].node_tree.links 
	decal_bsdf = nodes.get('instantproject_decal_bsdf')
	if decal_bsdf is None:
		self.report({'WARNING'}, 'No Decal Layer found, aborting.')
		return{'CANCELLED'}

	# Grab Relevent Nodes
	material_output = nodes.get('Material Output')
	decal_mix = nodes.get('instantproject_decal_mix')
	decal_image_node = nodes.get('instantproject_decal_image')
	original_bsdf = nodes.get('original_bsdf')

	nodes.remove(decal_bsdf)
	nodes.remove(decal_image_node)
	nodes.remove(decal_mix)

	link = links.new(original_bsdf.outputs[0], material_output.inputs[0])

	brush = bpy.context.tool_settings.image_paint.brush
	brush.texture_slot.map_mode = 'TILED'
	brush.texture = None
	return{'FINISHED'}

#--------------------------------------------------------------
# Camera Projection Tools
#--------------------------------------------------------------		
class INSTANTPROJECT_OT_setBackgroundImage(bpy.types.Operator, ImportHelper):
	# Opens a File Browser to select an Image that will be assigned as the Active Camera's Background Image for Projection.
	bl_idname = 'instantproject.set_background_image'
	bl_label = 'Select Projection Image'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Select an Image File for Camera Projection'

	filter_glob: bpy.props.StringProperty(
			default='*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp;',
			options={'HIDDEN'}
		)

	def execute(self, context):
		# Camera Safety Check
		camera = bpy.context.scene.camera
		if not camera: # Safety Check
			self.report({'WARNING'}, 'No active scene camera.')
			return{'CANCELLED'}	

		# Image Loading
		image = load_image(self.filepath, check_existing=True)

		camera.data.show_background_images = True 
		camera.data.background_images.clear()
		bg_image = camera.data.background_images.new()
		bg_image.image = image
		camera.data.background_images[0].frame_method = 'FIT'

		camera.data.background_images[0].display_depth = 'FRONT'
		return {'FINISHED'}	

class INSTANTPROJECT_OT_matchBackgroundImageResolution(bpy.types.Operator):
	# Clears all Background Images.
	bl_idname = 'instantproject.match_background_image_resolution'
	bl_label = 'Match Scene Resolution to Background'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Adjusts the Scene Resolution to match the current Background Image'

	def execute(self, context):
		# Safety Checks
		camera = bpy.context.scene.camera
		if camera.data.show_background_images == False or len(camera.data.background_images) == 0 or camera.data.background_images[0].image is None:
			self.report({'WARNING'}, 'No background image assigned to camera.')
			return{'CANCELLED'}

		background_image = camera.data.background_images[0]	
		width = background_image.image.size[0]	
		height = background_image.image.size[1]
		
		bpy.data.scenes[0].render.resolution_x = width
		bpy.data.scenes[0].render.resolution_y = height
		return{'FINISHED'}

class INSTANTPROJECT_OT_clearBackgroundImages(bpy.types.Operator):
	# Clears all Background Images.
	bl_idname = 'instantproject.clear_background_image'
	bl_label = 'Clear Projection Images'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = 'Removes background images from Camera.'

	def execute(self, context):
		# Camera Safety Check
		camera = bpy.context.scene.camera
		if not camera: # Safety Check
			self.report({'WARNING'}, 'No active scene camera.')
			return{'CANCELLED'}	

		if camera.data.show_background_images == False or len(camera.data.background_images) == 0 or camera.data.background_images[0].image is None:
			self.report({'WARNING'}, 'No background image assigned to camera.')
			return{'CANCELLED'}

		camera.data.background_images.clear() 
		camera.data.show_background_images = False
		return{'FINISHED'}

class INSTANTPROJECT_OT_projectImage(bpy.types.Operator):
	# Projects an edited Render from the active camera back onto the Object.
	bl_idname = 'instantproject.project_image'
	bl_label = 'Project Image'
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Projects the Camera's Background Image onto the selected Object"

	project_resolution: bpy.props.FloatProperty(name='project_resolution', default=0.25)

	@classmethod
	def poll(cls, context):
		return context.mode in ['PAINT_TEXTURE', 'OBJECT', 'EDIT_MESH']
	
	def execute(self, context):
		if bpy.context.active_object is None:
			self.report({'WARNING'}, 'Please select a Target Object.')
			return{'CANCELLED'}					
		if bpy.context.scene.camera is None:
			self.report({'WARNING'}, 'No active scene camera.')
			return{'CANCELLED'}		
		
		# Safety Checks
		active_object = bpy.context.active_object
		camera = bpy.context.scene.camera
		if camera.data.show_background_images == False or len(camera.data.background_images) == 0 or camera.data.background_images[0].image is None:
			self.report({'WARNING'}, 'No background image assigned to camera.')
			return{'CANCELLED'}

		background_image = camera.data.background_images[0]	

		width = int(background_image.image.size[0] * self.project_resolution)
		height = int(background_image.image.size[1] * self.project_resolution)
		previous_mode = context.mode

		# Create Material & Unwrap
		active_object.data.materials.clear()
		name = f'{background_image.image.name}_projection'
		material = bpy.data.materials.new(name=name)
		material.use_nodes = True
		active_object.data.materials.append(material)
		nodes = material.node_tree.nodes
		links = material.node_tree.links

		projection_image = bpy.data.images.new(name=name, width=width, height=height)
		pixels = [1.0] * (4 * width * height)
		projection_image.pixels = pixels
	
		INSTANTPROJECT_FN_setShaders(nodes, links, projection_image)

		# Select Image for Projection
		node_albedo = nodes.get('albedo')
		node_albedo.select = True   
		nodes.active = node_albedo
	    
		if not context.mode == 'EDIT':
			bpy.ops.object.mode_set(mode='EDIT')
		bpy.ops.mesh.select_all(action='SELECT')	
		#bpy.ops.uv.project_from_view(camera_bounds=True, correct_aspect=False, scale_to_bounds=True)
		bpy.ops.uv.smart_project(scale_to_bounds=True)

		if not context.mode == 'PAINT_TEXTURE':
			bpy.ops.object.mode_set(mode='TEXTURE_PAINT')

		# Set to Image Mode for Painting
		bpy.context.scene.tool_settings.image_paint.mode = 'IMAGE'
		bpy.context.scene.tool_settings.image_paint.canvas = projection_image

		bpy.ops.wm.tool_set_by_id(name='builtin_brush.Fill')
		bpy.ops.paint.project_image(image=background_image.image.name)
		bpy.ops.image.save_all_modified()

		if previous_mode == 'EDIT':
			bpy.ops.object.mode_set(mode='EDIT')
		else:
			bpy.ops.object.mode_set(mode='OBJECT')

		# Select Albedo
		node_albedo.select = True   
		nodes.active = node_albedo
		return {'FINISHED'}	

class INSTANTPROJECT_OT_saveAllImages(bpy.types.Operator):
	# Saves all edited Image files.
	bl_idname = 'instantproject.save_all_images'
	bl_label = 'Save All'
	bl_description = 'Saves all modified images'
	bl_options = {'REGISTER'}

	def execute(self, context):
		try:
			bpy.ops.image.save_all_modified()
			self.report({'INFO'}, 'Images saved successfully.')
		except:
			self.report({'WARNING'}, 'Images unchanged, no save necessary.')
			return {'CANCELLED'}
		return {'FINISHED'}

class INSTANTPROJECT_OT_clearUnused(bpy.types.Operator):
	# Purges unused Data Blocks.
	bl_idname = 'instantproject.clear_unused'
	bl_label = 'Clear Unused'
	bl_description = 'Removes unlinked data from the Blend File. WARNING: This process cannot be undone'
	bl_options = {'REGISTER'}

	def execute(self, context):
		bpy.ops.outliner.orphans_purge('INVOKE_DEFAULT' if True else 'EXEC_DEFAULT', num_deleted=0, do_local_ids=True, do_linked_ids=False, do_recursive=True)
		return {'FINISHED'}

# ==============================================
# Decals
# ==============================================

class INSTANTPROJECT_OT_addDecalLayer(bpy.types.Operator, ImportHelper):
	# Loads the selected Image to the Texture Paint Texture Slot, then extends the Shader Tree to use it as a Decal
	bl_idname = 'instantproject.load_image_and_setup_texture_mask'
	bl_label = 'Load Texture Mask'
	bl_description = 'Extends the Shader Tree and assigns the selected image as a Decal'
	bl_options = {'REGISTER', 'UNDO'}

	filter_glob: bpy.props.StringProperty(
			default='*.jpg;*.jpeg;*.png;*.tif;*.tiff;*.bmp;',
			options={'HIDDEN'}
		)

	project_resolution: bpy.props.FloatProperty(name='project_resolution', default=0.25)

	@classmethod
	def poll(cls, context):
		return context.mode in ['PAINT_TEXTURE', 'OBJECT', 'EDIT_MESH']

	def execute(self, context):
		# Image Loading
		image = load_image(self.filepath, check_existing=True)

		# Safety Checks
		active_object = bpy.context.active_object
		if not active_object:
			self.report({'WARNING'}, 'No active object selected.')
			return{'CANCELLED'}

		if len(active_object.data.materials) < 1:
			material = bpy.data.materials.new(name=image.name)
			active_object.data.materials.append(material)

		material = active_object.data.materials[0]
		material.use_nodes = True
		nodes = active_object.data.materials[0].node_tree.nodes 
		links = active_object.data.materials[0].node_tree.links 

		# Grab Relevent Nodes
		material_output = nodes.get('Material Output')
		original_bsdf = material_output.inputs[0].links[0].from_node

		# Check for Existing Decal Setup
		if nodes.get('instantproject_decal_bsdf') is None:
			# Safety Checks 
			if original_bsdf == None:
				self.report({'WARNING'}, 'No valid Node Found, aborting.')
				return{'CANCELLED'}
			if not original_bsdf.bl_idname in {'ShaderNodeBsdfPrincipled', 'ShaderNodeEmission', 'ShaderNodeMixShader', 'ShaderNodeAddShader', 'ShaderNodeBsdfDiffuse', 'ShaderNodeBsdfGlossy'}:
				self.report({'WARNING'}, 'No valid Node found, aborting.')
				return{'CANCELLED'}

			# Extend Shader
			original_bsdf.name = 'original_bsdf'
			links.remove(material_output.inputs[0].links[0])
			decal_bsdf = nodes.new(type=original_bsdf.bl_idname)

			if original_bsdf.bl_idname == 'ShaderNodeEmission':
				decal_bsdf = nodes.new(type='ShaderNodeEmission')
			else:
				decal_bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
				decal_bsdf.hide = True
			decal_bsdf.name = 'instantproject_decal_bsdf'
			decal_mix = nodes.new(type='ShaderNodeMixShader')
			decal_mix.name = 'instantproject_decal_mix'
			decal_image_node =  nodes.new(type='ShaderNodeTexImage')
			decal_image_node.name = 'instantproject_decal_image'	

			# Repeposition Nodes		
			material_output.location = Vector((original_bsdf.location[0] + 1200, original_bsdf.location[1]))
			decal_mix.location = Vector((material_output.location[0] - (material_output.width + 50), material_output.location[1]))
			decal_bsdf.location = Vector((decal_mix.location[0] - (decal_bsdf.width + 50), decal_mix.location[1] - 300))
			decal_image_node.location = Vector((decal_bsdf.location[0] - 300, decal_bsdf.location[1]))

			# Setup New Links
			link = links.new(original_bsdf.outputs[0], decal_mix.inputs[1])
			link = links.new(decal_bsdf.outputs[0], decal_mix.inputs[2])
			link = links.new(decal_image_node.outputs[0], decal_bsdf.inputs[0])
			link = links.new(decal_image_node.outputs[1], decal_mix.inputs[0])
			link = links.new(decal_mix.outputs[0], material_output.inputs[0])
		else:
			decal_bsdf = nodes.get('instantproject_decal_bsdf')
			decal_mix = nodes.get('instantproject_decal_mix')
			decal_image_node = nodes.get('instantproject_decal_image')	
			self.report({'INFO'}, 'Shader already has Decal setup.')
							


		# Assign Image as Stencil and enter Paint Mode
		if not context.mode == 'PAINT_TEXTURE':
			bpy.ops.object.mode_set(mode='TEXTURE_PAINT')

		decal_texture = bpy.data.textures.new(name='my_texture', type='IMAGE')
		decal_texture.image = image
		
		width = int(context.scene.render.resolution_x * self.project_resolution)
		height = int(context.scene.render.resolution_y * self.project_resolution)
		decal_layer_image = bpy.data.images.new(name='my_decal_image', width=width, height=height)
		pixels = [0.0] * (4 * width * height)
		decal_layer_image.pixels = pixels

		# Select Correct Image for Painting
		decal_image_node.image = decal_layer_image
			
		bpy.ops.wm.tool_set_by_id(name='builtin_brush.Draw')
		brush = bpy.context.tool_settings.image_paint.brush
		brush.texture = decal_texture
		brush.texture_slot.map_mode = 'STENCIL'

		# Set to Image Mode for Painting (Yuck)
		bpy.context.scene.tool_settings.image_paint.mode = 'IMAGE'
		bpy.context.scene.tool_settings.image_paint.canvas = decal_layer_image

		bpy.ops.brush.stencil_reset_transform()
		bpy.ops.brush.stencil_fit_image_aspect()
		return {'FINISHED'}		

class INSTANTPROJECT_OT_unloadDecal(bpy.types.Operator):
	# Loads the selected Image to the Texture Paint Texture Slot, then extends the Shader Tree to use it as a Decal
	bl_idname = 'instantproject.unload_decal'
	bl_label = 'Unload Decal'
	bl_description = 'Unloads the Decal Image from the Stencil.'
	bl_options = {'REGISTER', 'UNDO'}

	@classmethod
	def poll(cls, context):
		return context.mode in ['PAINT_TEXTURE', 'OBJECT', 'EDIT_MESH']

	def execute(self, context):
		# Safety Check
		active_object = bpy.context.active_object
		if not active_object:
			self.report({'WARNING'}, 'No active object selected.')
			return{'CANCELLED'}
		try:
			brush = bpy.context.tool_settings.image_paint.brush
			brush.texture_slot.map_mode = 'TILED'
			brush.texture = None
		except:
			return{'CANCELLED'}		
		return {'FINISHED'}	

class INSTANTPROJECT_OT_toggleDecalVisibility(bpy.types.Operator):
	# Toggles the visibility of the Decal Layer
	bl_idname = 'instantproject.toggle_decal_visibility'
	bl_label = 'Hide/Show Decal'
	bl_description = 'Toggles the visibility of the Decal Layer.'
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		active_object = bpy.context.active_object
		if not active_object:
			self.report({'WARNING'}, 'No active object selected.')
			return{'CANCELLED'}
		try:
			nodes = active_object.data.materials[0].node_tree.nodes 
			mix = nodes.get('instantproject_decal_mix')
			mix.mute = 1-mix.mute
		except:
			return{'CANCELLED'}
		return{'FINISHED'}

class INSTANTPROJECT_OT_removeDecalLayer(bpy.types.Operator):
	# Confirmation Popup when Deleting Decal Layer
	bl_idname = 'instantproject.confirm_delete'
	bl_label = 'This will revert the Shader, continue?'
	bl_description = 'Removes the Decal Layer and reverts the Shader to its original state.'
	bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

	@classmethod 
	def poll(cls, context):
		return True 

	def execute(self, context):
		self.report({'INFO'}, "Continue.")
		INSTANTPROJECT_FN_removeDecalLayer(self, context)
		return{'FINISHED'}

	def invoke(self, context, event):
		return context.window_manager.invoke_confirm(self, event)


#--------------------------------------------------------------
# Interface
#--------------------------------------------------------------

class INSTANTPROJECT_PT_panelMain(bpy.types.Panel):
	bl_label = 'InstantProject'
	bl_idname = 'INSTANTPROJECT_PT_panelMain'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'InstantProject'

	def draw(self, context):
		layout = self.layout		

class INSTANTPROJECT_PT_panelCameraProjection(bpy.types.Panel):
	bl_label = 'Camera Projection'
	bl_idname = 'INSTANTPROJECT_PT_panelCameraProjection'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'InstantProject'
	bl_parent_id = 'INSTANTPROJECT_PT_panelMain'

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.operator(INSTANTPROJECT_OT_setBackgroundImage.bl_idname, text='Open Image', icon='FILE_FOLDER')
		row.operator(INSTANTPROJECT_OT_matchBackgroundImageResolution.bl_idname, text='Match Scene', icon='RESTRICT_VIEW_OFF')
		row = layout.row()
		button_project_image = row.operator(INSTANTPROJECT_OT_projectImage.bl_idname, text='Project To Mesh', icon_value=727)
		row.operator(INSTANTPROJECT_OT_clearBackgroundImages.bl_idname, text='', icon='CANCEL')			
		row = layout.row()		
		button_project_image.project_resolution = context.scene.INSTANTPROJECT_VAR_projectResolution

class INSTANTPROJECT_PT_panelDecalLayers(bpy.types.Panel):
	bl_label = 'Decal Layers'
	bl_idname = 'INSTANTPROJECT_PT_panelDecalLayers'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'InstantProject'
	bl_parent_id = 'INSTANTPROJECT_PT_panelMain'

	def draw(self, context):
		active_object = context.active_object
		if active_object is None:
			return		
		layout = self.layout
		row = layout.row()		
		button_load_decal_layer = row.operator(INSTANTPROJECT_OT_addDecalLayer.bl_idname, text='Load Decal', icon_value=727)
		button_load_decal_layer.project_resolution = context.scene.INSTANTPROJECT_VAR_projectResolution				
		button_unload_decal = row.operator(INSTANTPROJECT_OT_unloadDecal.bl_idname, text='Unload Decal', icon='CANCEL')
		try:
			nodes = active_object.data.materials[0].node_tree.nodes
		except:
			return
		if nodes.get('instantproject_decal_mix') is not None:
			button_hide_decal_layer = row.operator(INSTANTPROJECT_OT_toggleDecalVisibility.bl_idname, text='', icon='HIDE_ON' if nodes.get('instantproject_decal_mix').mute else 'HIDE_OFF')
		button_remove_decal_layer = row.operator(INSTANTPROJECT_OT_removeDecalLayer.bl_idname, text='', icon_value=21)

class INSTANTPROJECT_PT_panelFileManagement(bpy.types.Panel):
	bl_label = 'File Management'
	bl_idname = 'INSTANTPROJECT_PT_panelFileManagement'
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'InstantProject'
	bl_parent_id = 'INSTANTPROJECT_PT_panelMain'

	def draw(self, context):
		layout = self.layout
		row = layout.row()
		row.operator(INSTANTPROJECT_OT_saveAllImages.bl_idname, text='Save All', icon_value=727)
		row.operator(INSTANTPROJECT_OT_clearUnused.bl_idname, text='Clear Unused', icon_value=21)
		row = layout.row()
		row.prop(context.scene, 'INSTANTPROJECT_VAR_projectResolution', text='Scale Factor')


#--------------------------------------------------------------
# Register 
#--------------------------------------------------------------

classes = ()

classes_interface = (INSTANTPROJECT_PT_panelMain, INSTANTPROJECT_PT_panelCameraProjection, INSTANTPROJECT_PT_panelDecalLayers, INSTANTPROJECT_PT_panelFileManagement)
classes_functionality = (INSTANTPROJECT_OT_saveAllImages, INSTANTPROJECT_OT_clearUnused)
classes_projection = (INSTANTPROJECT_OT_setBackgroundImage, INSTANTPROJECT_OT_matchBackgroundImageResolution, INSTANTPROJECT_OT_clearBackgroundImages, INSTANTPROJECT_OT_projectImage, )
classes_decal = (INSTANTPROJECT_OT_addDecalLayer, INSTANTPROJECT_OT_unloadDecal, INSTANTPROJECT_OT_toggleDecalVisibility, INSTANTPROJECT_OT_removeDecalLayer)

def register():

	# Register Classes
	for c in classes_interface:
		bpy.utils.register_class(c)
	for c in classes_functionality:
		bpy.utils.register_class(c)
	for c in classes_projection:
		bpy.utils.register_class(c)
	for c in classes_decal:
		bpy.utils.register_class(c)

	# Variables
	bpy.types.Scene.INSTANTPROJECT_VAR_projectResolution = bpy.props.FloatProperty(name='INSTANTPROJECT_VAR_projectResolution', default=0.25, soft_min=0.1, soft_max=1.0, description='Resolution scaling factor for projected texture.')

			
def unregister():

	# Unregister
	for c in reversed(classes_interface):
		bpy.utils.unregister_class(c)
	for c in reversed(classes_functionality):
		bpy.utils.unregister_class(c)
	for c in reversed(classes_projection):
		bpy.utils.unregister_class(c)
	for c in reversed(classes_decal):
		bpy.utils.unregister_class(c)		
	
	# Variables

	del bpy.types.Scene.INSTANTPROJECT_VAR_projectResolution

if __name__ == '__main__':
	register()